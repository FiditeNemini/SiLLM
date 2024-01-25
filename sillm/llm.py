import pathlib
import logging

import mlx.core as mx
import mlx.nn as nn
from mlx.utils import tree_flatten, tree_unflatten

import sillm.args
import sillm.llama as llama
import sillm.mixtral as mixtral
import sillm.utils as utils

class LLM():
    """
    LLM model wrapper.
    """
    def __init__(self,
                 tokenizer,
                 args: sillm.args.ModelArgs
                 ):
        """
        Args:
            tokenizer: Tokenizer instance.
            args: Model arguments.
        """
        self.args = args

        if args.model_type == "llama":
            self.model = llama.Model(args)
        elif args.model_type == "mistral":
            self.model = llama.Model(args)
        elif args.model_type == "mixtral":
            self.model = mixtral.Model(args)
        else:
            raise NotImplementedError(f"Model type {args.model_type} is not supported")
        self.tokenizer = tokenizer

        self._quantization = None
        if args.quantization is not None:
            self.quantize(group_size=args.quantization["group_size"], bits=args.quantization["bits"])

    def load_weights(self,
                     model_path,
                     verify: bool = True):
        """
        Load model weights.
        Args:
            model_path: Path to model weights.
        """
        if isinstance(model_path, str):
            model_path = pathlib.Path(model_path)

        weights_files = []
        if model_path.is_file():
            weights_files = [model_path]
        elif model_path.is_dir():
            weights_files_npz = list(model_path.glob("*.npz"))
            weights_files_safetensors = list(model_path.glob("*.safetensors"))
            weights_files_bin = list(model_path.glob("*.bin"))

            if len(weights_files_npz) > 0:
                weights_files = weights_files_npz
            elif len(weights_files_safetensors) > 0:
                weights_files = weights_files_safetensors
            elif len(weights_files_bin) > 0:
                weights_files = weights_files_bin
            else:
                raise ValueError("No weights files found")
    
        weights = {}
        for weights_path in weights_files:
            logging.debug(f"Loading model weights file {weights_path}")

            weights_path = pathlib.Path(weights_path)
            if weights_path.suffix == ".npz" or weights_path.suffix == ".safetensors":
                weights_buffer = mx.load(str(weights_path))
            elif weights_path.suffix == ".bin":
                weights_buffer = utils.load_torch(str(weights_path))

            for k, v in weights_buffer.items():
                k = utils.map_key(k)

                if k:
                    weights[k] = v
                else:
                    logging.warning(f"Unknown key: {k}")
        total_params = sum(v.size for v in weights.values())

        if verify:
            self.verify_weights(weights)
        
        weights = tree_unflatten(list(weights.items()))
        self.model.update(weights)

        mx.eval(self.model.parameters())

        logging.info(f"Loaded model weights with {total_params/10**9:.2f}B total parameters")

    def save_npz(self, weights_path: str):
        """
        Save model weights.
        Args:
            weights_path: Path to weights file.
        """
        self.model.save_weights(weights_path)

        logging.info(f"Saved model weights to {weights_path}")

    def quantize(self,
                 group_size: int = 64,
                 bits: int = 4
                 ):
        """
        Quantize model.
        Args:
            group_size: Group size for quantization.
            bits: Number of bits for quantization.
        """
        if self._quantization is None:
            quantization = {
                "group_size": group_size,
                "bits": bits
            }
            self._quantization = quantization

            nn.QuantizedLinear.quantize_module(
                model = self.model,
                **quantization,
                linear_class_predicate = lambda m: isinstance(m, nn.Linear) and m.weight.shape[0] != 8
            )

            logging.info(f"Quantized model with group size {group_size} and {bits} bits")
        else:
            logging.warn(f"Model is already quantized")

    def dequantize(self):
        """
        Dequantize model.
        """
        if self._quantization is not None:
            layers = []
            for name, module in self.model.named_modules():
                if isinstance(module, nn.QuantizedLinear):
                    bias = "bias" in module
                    weight = module.weight()
                    weight = mx.dequantize(weight, module.scales, module.biases, module.group_size, module.bits).astype(mx.float16)
                    output_dims, input_dims = weight.shape
                    linear = nn.Linear(input_dims, output_dims, bias=bias)
                    linear.weight = weight
                    if bias:
                        linear.bias = module.bias

                    layers.append((name, linear))
            
            self.model.update_modules(tree_unflatten(layers))
            self._quantization = None

            logging.info(f"Dequantized model")

    def verify_weights(self, weights):
        """
        Verify weights for all modules are present.
        Args:
            weights: Weights to verify.
        """
        result = True
        for name, _ in tree_flatten(self.model.parameters()):
            if name not in weights:
                result = False

                logging.warn(f"Key {name} not found in weights")

        return result

    def generate(self,
                 prompt,
                 temp: float = 0.0,
                 num_tokens: int = 256,
                 flush: int = 5):
        """
        Iterator for generating tokens.
        Args:
            prompt: Prompt to start generation.
            temp: Sampling temperature.
            num_tokens: Max number of tokens to generate.
            flush: Flush every `flush` tokens.
        """
        logging.debug(f"Generating {num_tokens} tokens with temperature {temp} and flushing every {flush} tokens")

        prompt = mx.array(self.tokenizer.encode(prompt))

        def generate_step():
            def sample(logits):
                if temp == 0:
                    return mx.argmax(logits, axis=-1)
                else:
                    return mx.random.categorical(logits * (1 / temp))

            logits, cache = self.model(prompt[None])
            y = sample(logits[:, -1, :])
            yield y

            while True:
                logits, cache = self.model(y[:, None], cache)
                y = sample(logits.squeeze(1))
                yield y

        tokens = []
        for token, _ in zip(generate_step(), range(num_tokens)):
            if token[0] == self.tokenizer.eos_id:
                break
            tokens.append(token)

            if (len(tokens) % flush) == 0:
                mx.eval(tokens)
                s = self.tokenizer.decode([t.item() for t in tokens])

                yield s

                tokens = []

        mx.eval(tokens)
        s = self.tokenizer.decode([t.item() for t in tokens])

        yield s