![sillm](https://github.com/armbues/SiLLM/assets/4117144/859002e9-d209-480b-adb2-7276cd360cbe)

# SiLLM - Silicon LLM Training & Inference Toolkit
SiLLM simplifies the process of training and running Large Language Models (LLMs) on Apple Silicon by leveraging the [MLX](https://github.com/ml-explore/mlx/) framework. Building upon the foundation provided by [MLX Examples](https://github.com/ml-explore/mlx-examples), this project introduces additional features specifically designed to enhance LLM operations with MLX in a streamlined package.

- **LLM Loading**: load LLMs for chat and training in different formats (Huggingface, Torch, GGUF, MLX)
- **LoRA Training**: train LLMs using *Low-rank Adaptation*
- **DPO Training**: train LLMs with *Direct Preference Optimization*

## Features

- Web app for a seamless chat experience running on local hardware
- API server with OpenAI compatible chat endpoints
- Model architectures: Llama, Mistral, Mixtral, Phi-2, Phi-3, Gemma, Qwen2, Starcoder2, DBRX, Cohere Command-R
- Conversation templates: llama-2, chatml, alpaca, vicuna, gemma, phi, openchat
- Loss functions for DPO: sigmoid, hinge, IPO, DPOP
- Training loss plots using matplotlib
- Perplexity calculation

## Experimental
One of the main goals of SiLLM is to enable experimentation with the inner workings of large language models and make new techniques accessible to a wider audience running on Apple Silicon hardware.

### Control vectors and feature ablation
The control module incorporates techniques based on the paper [Representation Engineering](https://arxiv.org/abs/2310.01405) and the blog [Refusal Ablation](https://www.lesswrong.com/posts/jGuXSZgv6qfdhMCuJ/refusal-in-llms-is-mediated-by-a-single-direction). Representation engineering is a method to calculate control vectors from a model's hidden states during training that can be used to influence the behavior and generated output during inference. Refusal ablation works similarly, but can be used to remove the direction represented by the vector from model weights.

## Installation

Using pip:
``` sh
pip install sillm-mlx
```

## Usage

### Chat web application
The web app uses [Chainlit](https://github.com/Chainlit/chainlit) to provide a frontend for conversational AI running locally on Apple Silicon hardware.

https://github.com/armbues/SiLLM/assets/4117144/ab537795-5020-4241-aa89-3b19b9de263b

To use the web app, clone the repository and start the app using chainlit:
``` sh
git clone https://github.com/armbues/SiLLM.git
cd SiLLM/app
pip install -r requirements.txt
python -m chainlit run app.py -w
```
Set the environment variables `SILLM_MODEL_DIR` and `SILLM_ADAPTER_DIR` to load local models/adapters.

### Command-line interface (CLI) scripts
Run the CLI scripts with the argument -h to see a print-out of all available arguments.

#### Chat:
Simple CLI interface for chatting with an LLM in the terminal.
``` sh
python -m sillm.chat /path/to/model
```
Running sillm.chat in the terminal with Gemma-2B-it on a MacBook Air M2 with 16GB memory:

https://github.com/armbues/SiLLM/assets/4117144/42e2d0f8-3bd8-44ca-9f78-8c4a885b8939

#### Server:
Run an API server with basic functionality compatible with OpenAI compatible chat endpoints.
``` sh
python -m sillm.server /path/to/model --port 8000
```

#### LoRA Fine-tuning:
Fine-tune a model with low-rank adaptation (LoRA).
``` sh
python -m sillm.lora /path/to/model -d /path/to/dataset -o /output/adapters
```

#### DPO Fine-tuning:
Fine-tune a model with LoRA and direct preference optimization (DPO).
``` sh
python -m sillm.dpo /path/to/model -d /path/to/dataset -o /output/adapters
```

#### Conversion
Convert a model while merging adapters or quantizing the weights.

Example of merging an adapter into a model:
``` sh
python -m sillm.convert /path/to/input/model /path/to/output/model -a /path/to/adapters
```

#### Quantization
Quantize a model serially (without loading it entirely into memory):
``` sh
python -m sillm.quantize /path/to/input/model /path/to/output/model --bits 4
```

### Python
Minimal example of loading a model with SiLLM and generating a text completion:
``` python
import sillm

model = sillm.load("/path/to/model")
for s, _ in model.generate("On a beautiful Sunday morning,"):
    print(s, flush=True, end="")
```

### Examples

The repository [SiLLM-examples](https://github.com/armbues/SiLLM-examples) contains Python code examples for using the SiLLM framework for training and running LLMs.

#### LoRA Fine-tuning
LoRA training [Mistral-7B-Instruct-v0.2](https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.2) with the Nvidia [HelpSteer](https://huggingface.co/datasets/nvidia/HelpSteer) dataset.

#### DPO Fine-tuning
DPO training [Qwen1.5-7B-Chat](https://huggingface.co/Qwen/Qwen1.5-7B-Chat) with the [DPO Mix 7K](https://huggingface.co/datasets/argilla/dpo-mix-7k) dataset. The training consists of a supervised fine tuning (SFT) followed by direct preference optimization (DPO).

#### MMLU Benchmark
Implementation of the "Massive Multitask Language Understanding" benchmark using the [MMLU](https://huggingface.co/datasets/cais/mmlu) dataset.

#### Perplexity
Calculating perplexity scores for a sample [dataset](https://huggingface.co/datasets/Cohere/wikipedia-2023-11-embed-multilingual-v3) of entry paragraphs from Wikipedia articles.

## Model Support
SiLLM generally supports loading LLMs of the following model architectures/families: *Llama 2*, *Mistral*, *Mixtral*, *Gemma*, *Phi*, *Qwen 2*, *StarCoder2*.

Here is a list of significant models that were successfully tested with SiLLM:

| Model Family | Models/Sizes |
| --- | --- |
| Llama-3 | [8B-Instruct](https://huggingface.co/meta-llama/Meta-Llama-3-8B-Instruct), [70B-Instruct](https://huggingface.co/meta-llama/Meta-Llama-3-70B-Instruct/) |
| Phi-3 | [medium-4k-instruct](https://huggingface.co/microsoft/Phi-3-medium-4k-instruct) |
| Phi-3.5 | [mini-instruct](https://huggingface.co/microsoft/Phi-3.5-mini-instruct), [MoE-instruct](https://huggingface.co/microsoft/Phi-3.5-MoE-instruct) |
| Gemma-2 | [2b-it](https://huggingface.co/google/gemma-2-2b-it), [9b-it](https://huggingface.co/google/gemma-2-9b-it), [27b-it](https://huggingface.co/google/gemma-2-27b-it) |
| Mistral | [7b-instruct-v0.3](https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3), [Nemo-Instruct](https://huggingface.co/mistralai/Mistral-Nemo-Instruct-2407), [Small-Instruct](https://huggingface.co/mistralai/Mistral-Small-Instruct-2409), [Large-Instruct](https://huggingface.co/mistralai/Mistral-Large-Instruct-2407) |
| Mixtral | [8x22B-Instruct-v0.1](https://huggingface.co/mistralai/Mixtral-8x22B-Instruct-v0.1) |
| Codestral | [22b-v0.1](https://huggingface.co/mistralai/Codestral-22B-v0.1) |
| Qwen 2 | [7b-instruct](https://huggingface.co/Qwen/Qwen2-7B-Instruct), [72b-instruct](https://huggingface.co/Qwen/Qwen2-72B-Instruct) |
| StarCoder2 | [3b](https://huggingface.co/bigcode/starcoder2-3b), [7b](https://huggingface.co/bigcode/starcoder2-7b), [15b](https://huggingface.co/bigcode/starcoder2-15b) |

## Roadmap

- Learning rate schedulers for training
- Merging models
- Saving models to GGUF
- Fine tuning with ORPO

## License
This project uses the [MIT License](LICENSE).

## Acknowledgments
Big thanks to the Apple MLX team for implementing and maintaining the [MLX](https://github.com/ml-explore/mlx/) framework that makes it possible to unlock the power of Apple Silicon and run/train LLMs on MacBooks and other Apple devices. Thank you to all the contributors of the [MLX Examples](https://github.com/ml-explore/mlx-examples) project and developers sharing model implementations online.
Last but not least, thank you to the larger community sharing open weights models, fine tunes, and datasets - without you all the gen AI progress would happen behind locked doors!
