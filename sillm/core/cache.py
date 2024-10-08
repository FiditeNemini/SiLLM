import collections
import hashlib
import logging

from typing import Optional

import mlx.core as mx

logger = logging.getLogger("sillm")

########
# Based on mlx-examples:
# https://github.com/ml-explore/mlx-examples/blob/fc93c557238e9441835afe2748fd170016cb068b/llms/mlx_lm/models/base.py#L11
########
class KVCache:
    @staticmethod
    def for_model(model):
        kv_heads = ([model.args.n_kv_heads] * model.args.n_layers)

        return [KVCache(model.args.head_dim, n) for n in kv_heads]

    def __init__(self,
                 head_dim,
                 n_kv_heads,
                 step : int = 256
                 ):
        self.n_kv_heads = n_kv_heads
        if isinstance(head_dim, int):
            self.k_head_dim = self.v_head_dim = head_dim
        elif isinstance(head_dim, tuple) and len(head_dim) == 2:
            self.k_head_dim, self.v_head_dim = head_dim
        else:
            raise ValueError("head_dim must be an int or a tuple of two ints")
        
        self.keys = None
        self.values = None
        self.offset = 0
        self.step = step

    def update_and_fetch(self,
                         keys,
                         values
                         ):
        prev = self.offset
        if self.keys is None or (prev + keys.shape[2]) > self.keys.shape[2]:
            B = keys.shape[0]
            n_steps = (self.step + keys.shape[2] - 1) // self.step

            k_shape = (B, self.n_kv_heads, n_steps * self.step, self.k_head_dim)
            v_shape = (B, self.n_kv_heads, n_steps * self.step, self.v_head_dim)

            new_k = mx.zeros(k_shape, keys.dtype)
            new_v = mx.zeros(v_shape, values.dtype)
            
            if self.keys is not None:
                if prev % self.step != 0:
                    self.keys = self.keys[..., :prev, :]
                    self.values = self.values[..., :prev, :]
                self.keys = mx.concatenate([self.keys, new_k], axis=2)
                self.values = mx.concatenate([self.values, new_v], axis=2)
            else:
                self.keys, self.values = new_k, new_v

        self.offset += keys.shape[2]
        self.keys[..., prev : self.offset, :] = keys
        self.values[..., prev : self.offset, :] = values

        return self.keys[..., : self.offset, :], self.values[..., : self.offset, :]
    
    def copy(self):
        new = KVCache(self.k_head_dim, self.n_kv_heads, self.step)
        
        if self.keys is not None:
            new.keys = mx.array(self.keys)
        if self.values is not None:
            new.values = mx.array(self.values)
        new.offset = self.offset

        return new

    @property
    def state(self):
        return self.keys, self.values

class PromptCache():
    """
    Cache for prompt logits and KV cache.
    """
    def __init__(self,
                 max_size: int = 10
                 ):
        self.logits = {}
        self.kv_cache = {}

        self.lru = collections.OrderedDict()

        self.max_size = max_size

        # TODO make multi-thread safe?

    def _key(self,
             inputs: mx.array
             ):
        return hashlib.sha256(inputs).hexdigest()
    
    def put(self,
            inputs: mx.array,
            logits: mx.array,
            kv_cache: Optional[KVCache] = None,
            ):
        """
        Add cache entry.
        """
        key = self._key(inputs)

        logger.debug(f"Adding prompt cache entry for key {key}")

        if key not in self.lru:
            self.logits[key] = logits
            self.kv_cache[key] = [c.copy() for c in kv_cache]
            self.lru[key] = 0

        if len(self.lru) > self.max_size:
            pop_key, _ = self.lru.popitem(last=False)
            self.logits.pop(pop_key)
            self.kv_cache.pop(pop_key)

    def get(self,
            inputs: mx.array|str
            ):
        """
        Get cache entry.
        """
        if type(inputs) is mx.array:
            key = self._key(inputs)
        else:
            key = inputs

        if key in self.lru:
            # Update LRU
            self.lru.move_to_end(key)
            self.lru[key] += 1

            logits = self.logits[key]
            kv_cache = [c.copy() for c in self.kv_cache[key]]

            logger.debug(f"Retrieving prompt cache entry for key {key}")
            
            return logits, kv_cache
        
        return None, None