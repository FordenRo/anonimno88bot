from logging import Filter, INFO


class InfoFilter(Filter):
    def filter(self, record):
        return record.levelno != INFO
