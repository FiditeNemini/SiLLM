import os
import pathlib

import chainlit as cl
from chainlit.input_widget import Select, Slider, TextInput

import sillm
import sillm.utils as utils

log_level = 10
logger = utils.init_logger(log_level, "%(asctime)s - %(message)s", add_stdout=False)

# Initialize model paths
MODEL_DIR = os.environ.get("SILLM_MODEL_DIR")
if MODEL_DIR is None:
    raise ValueError("Please set the environment variable SILLM_MODEL_DIR to the directory containing the models.")
MODEL_PATHS = {model_path.name: model_path for model_path in pathlib.Path(MODEL_DIR).iterdir() if model_path.is_dir() or model_path.suffix == ".gguf"}

ADAPTER_DIR = os.environ.get("SILLM_ADAPTER_DIR")
if ADAPTER_DIR is None:
    ADAPTER_PATHS = {}
else:
    ADAPTER_PATHS = {adapter_path.stem: adapter_path for adapter_path in pathlib.Path(ADAPTER_DIR).iterdir() if adapter_path.suffix == ".safetensors"}

models = {}
@cl.step(name="Loading Model")
async def load_model(model_name: str,
                     adapter_name: str = None
                     ):
    model = await cl.make_async(sillm.load)(MODEL_PATHS[model_name])
    msg = f"Loaded model {model_name}."
    model_id = model_name

    if adapter_name is not None and adapter_name in ADAPTER_PATHS:
        adapter_path = str(ADAPTER_PATHS[adapter_name])

        model = sillm.TrainableLoRA.from_model(model)
        lora_config = model.load_lora_config(adapter_path)
        model.init_lora(**lora_config)
        model.load_adapters(adapter_path)
        model.merge_and_unload_lora()

        msg = f"Loaded model {model_name} and adapters {adapter_name}."
        model_id = f"{model_name}:{adapter_name}"

    models[model_id] = model

    return msg

@cl.on_chat_start
async def on_chat_start():
    model_names = list(MODEL_PATHS.keys())
    model_names.sort()

    adapter_names = ["[none]"] + list(ADAPTER_PATHS.keys())
    adapter_names.sort()

    templates = ["[default]"] + [template.removesuffix(".jinja") for template in sillm.Template.list_templates()]
    templates.sort()

    settings = [
        Select(id="Model", label="Model", values=model_names, initial_index=0),
        Select(id="Adapter", label="Adapter", values=adapter_names, initial_index=0),
        Select(id="Template", label="Chat Template", values=templates, initial_index=0),
        Slider(id="Temperature", label="Model Temperature", initial=0.7, min=0, max=2, step=0.1),
        Slider(id="Penalty", label="Repetition Penalty", initial=1.0, min=0.1, max=3.0, step=0.1),
        Slider(id="Window", label="Repetition Window", initial=100, min=10, max=500, step=10),
        Slider(id="Tokens", label="Max. Tokens", initial=2048, min=256, max=8192, step=256),
        TextInput(id="Seed", label="Seed", initial="-1"),
    ]

    await cl.ChatSettings(settings).send()

    generate_args = {
        "temperature": 0.7,
        "max_tokens": 2048,
    }
    cl.user_session.set("generate_args", generate_args)

    cl.user_session.set("conversation", None)

@cl.on_settings_update
async def on_settings_update(settings):
    cl.user_session.set("model_name", settings["Model"])
    cl.user_session.set("template_name", settings["Template"])

    generate_args = {
        "temperature": settings["Temperature"],
        "max_tokens": settings["Tokens"],
    }
    if settings["Penalty"] != 1.0:
        generate_args["repetition_penalty"] = settings["Penalty"]
        generate_args["repetition_window"] = settings["Window"]
    cl.user_session.set("generate_args", generate_args)

    if "Adapter" in settings:
        cl.user_session.set("adapter_name", settings["Adapter"])

    seed = int(settings["Seed"])
    if seed >= 0:
        utils.seed(seed)

@cl.on_message
async def on_message(message: cl.Message):
    # Initialize model
    model_name = cl.user_session.get("model_name")
    adapter_name = cl.user_session.get("adapter_name")
    model_id = model_name
    if adapter_name != "[none]":
        model_id = f"{model_name}:{adapter_name}"
    if model_name is None:
        raise ValueError("Please select a model.")    
    if model_id not in models:
        await load_model(model_name, adapter_name)
    model = models[model_id]

    # Initialize conversation & templates
    conversation = cl.user_session.get("conversation")
    if conversation is None:
        template_name = cl.user_session.get("template_name")
        if template_name == "[default]":
            template_name = None

        template = sillm.init_template(model.tokenizer, model.args, template_name)
        conversation = sillm.Conversation(template)
        cl.user_session.set("conversation", conversation)

    # Initialize cache
    cache = cl.user_session.get("cache")
    if cache is None:
        cache = model.init_kv_cache()
        cl.user_session.set("cache", cache)

    # Add user message to conversation and get prompt string
    request = conversation.add_user(message.content)
    
    # Get model generation arguments
    generate_args = cl.user_session.get("generate_args")

    logger.debug(f"Generating {generate_args['max_tokens']} tokens with temperature {generate_args['temperature']}")

    # Generate response
    msg = cl.Message(author=model_id, content="")
    response = ""
    for s, _ in model.generate(request, cache=cache, **generate_args):
        await msg.stream_token(s)
        response += s
    await msg.send()

    # Add assistant message to conversation
    conversation.add_assistant(response)