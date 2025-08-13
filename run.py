"""Entry point for launching the Telegram racing bot."""

# The project used to expose a ``scripts.run_bot`` module but the directory was
# removed while the stub remained.  Import the main function directly from the
# ``bot`` module instead so the bot can be started via ``python run.py``.

from bot import main
if __name__ == "__main__":
    main()
