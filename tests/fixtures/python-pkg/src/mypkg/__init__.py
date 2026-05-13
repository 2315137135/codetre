"""Main module."""

class App:
    def __init__(self, config: dict):
        self.config = config
        self._init_logger()

    def _init_logger(self):
        import logging
        self.logger = logging.getLogger(__name__)

    def run(self):
        self.logger.info("starting")
        result = self._process()
        return result

    def _process(self):
        return {"status": "ok"}
