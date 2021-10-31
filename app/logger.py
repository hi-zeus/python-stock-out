# -*- coding: utf-8 -*-
import logging
import logging.handlers
import os
import json
from datetime import date, datetime


class Logger:
    def __init__(self,
                 log_dir,
                 task_name=None,
                 sub_name=None,
                 name_datetime: datetime = datetime.now(),
                 task_no=None,
                 worker_no=None,
                 raise_exceptions=True,
                 log_level='DEBUG',
                 stdout=False,
                 log_format="%(asctime)s | %(levelname)s | %(process)d | %(thread)d | %(funcName)s | %(message)s",
                 max_file_size=1024,
                 backup_file_count=1):
        self.task_name = task_name
        self.sub_name = sub_name
        self.name_datetime = name_datetime
        self.log_dir = log_dir
        self.log_level = log_level
        self.stdout = stdout
        self.log_format = log_format
        self.max_file_size = max_file_size
        self.backup_file_count = backup_file_count

        names = ['log']
        if self.task_name:
            names.append(self.task_name)
        names.append(self.name_datetime.strftime('%Y-%m-%d_%Hh%Mm%Ss'))
        if self.sub_name:
            names.append(self.sub_name)
        if task_no:
            names.append('task-{task_no}'.format(task_no=task_no))
        if worker_no:
            names.append('worker-{worker_no}'.format(worker_no=worker_no))
        self.name = '_'.join(names)

        # ロガーで例外の送出をするかどうか
        logging.raiseExceptions = raise_exceptions

        # ロガー初期化
        self._log_init()

    def _log_init(self):
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(self.log_level)

        # レコード形式
        formatter = logging.Formatter(self.log_format)

        # stdout
        if self.stdout:
            handler = logging.StreamHandler()
            handler.setLevel(self.log_level)
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)

        #  ログ保存ディレクトリ確認
        log_dir = '{log_base_dir}'.format(log_base_dir=self.log_dir)
        os.makedirs(log_dir, exist_ok=True)

        # logファイル名生成
        log_file_name_a = '{name}.log'.format(name=self.name)
        log_file = os.path.join(log_dir, log_file_name_a)
        handler = logging.handlers.RotatingFileHandler(
            filename=log_file,
            maxBytes=self.max_file_size,
            encoding='utf-8',
            backupCount=self.backup_file_count,
            delay=True)
        handler.setLevel(self.log_level)
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def debug(self, msg):
        self.logger.debug(msg)

    def info(self, msg):
        self.logger.info(msg)

    def warn(self, msg):
        self.logger.warning(msg)

    def error(self, msg):
        self.logger.error(msg)

    def critical(self, msg):
        self.logger.critical(msg)

    def exception(self, msg):
        self.logger.exception(msg)


def var_dump(data):
    def json_serial(obj):
        # 日付型の場合には、文字列に変換します
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        # 上記以外はサポート対象外.
        raise TypeError("Type %s not serializable" % type(obj))

    return json.dumps(data, ensure_ascii=False, default=json_serial)
