"""Web layer for the university assistant demo."""


def main() -> None:
    """Run the demo web server."""
    from demo.web.server import main as web_main

    web_main()


__all__ = ["main"]
