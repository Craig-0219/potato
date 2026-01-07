import importlib,sys
modules=['interaction_helper','error_handler','vote_utils','embed_builder']
for name in modules:
    try:
        m=importlib.import_module(f'potato_bot.utils.{name}')
        sys.modules[f'bot.utils.{name}']=m
        globals()[name]=m
    except ModuleNotFoundError:
        continue

