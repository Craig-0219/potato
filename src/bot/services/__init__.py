import importlib,sys
modules=['data_cleanup_manager','welcome_manager','game_manager','economy_manager','lottery_manager','ticket_manager','webhook_manager','assignment_manager','system_monitor']
for name in modules:
    try:
        m=importlib.import_module(f'potato_bot.services.{name}')
        sys.modules[f'bot.services.{name}']=m
        globals()[name]=m
    except ModuleNotFoundError:
        continue
