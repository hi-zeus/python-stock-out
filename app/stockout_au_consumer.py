# -*- coding: utf-8 -*-

import argparse
from datetime import datetime
from typing import Dict
import functools

import const
import logger
from mq import MQ, MQMsgData
import auapi


def _stockout(msg_data: MQMsgData, log: logger.Logger):
    set_list = []
    item_ids = msg_data.item_ids
    for item_id in item_ids:
        set_data = auapi.AuUpdateStockData(item_code=item_id, stock_count=0)
        set_list.append(set_data)

    with auapi.AuAPI(log=log) as api:
        try:
            result = api.stock.update(update_items=set_list)
        except Exception:
            log.exception('Failed to update stock')
            raise
    log.info('Update stock data={data}'.format(data=set_list))
    log.info('No update stock data={data}'.format(data=result))


def _relist_on_message(msg: Dict, log: logger.Logger) -> bool:
    log.info('Message data={data}'.format(data=logger.var_dump(msg)))
    try:
        msg_data = MQMsgData(**msg)
    except Exception:
        raise Exception('Receive message parse error')
    log.info('Get queue message data={data}'.format(data=msg_data))

    _stockout(msg_data=msg_data, log=log)
    return True


def _consumer(log: logger.Logger):
    try:
        with MQ(**const.MQ_CONNECT,
                queue=const.MQ_AU_QUEUE,
                routing_key=const.MQ_AU_ROUTING_KEY) as queue:
            queue.open()
            callback = functools.partial(_relist_on_message, log=log)
            queue.receive_message(callback)

    except Exception:
        log.exception('Failed to MQ connect')
        raise


def main():
    parser = argparse.ArgumentParser(description='stockout_au_consumer')
    parser.add_argument('--task_no',
                        required=True,
                        type=int,
                        help='input process No type integer')

    arg_parser = parser.parse_args()

    # ログ
    log = logger.Logger(task_name='stockout-au-consumer',
                        sub_name='main',
                        name_datetime=datetime.now(),
                        task_no=arg_parser.task_no,
                        **const.LOG_SETTING)
    log.info('Start task')
    log.info('Input args task_no={task_no}'.format(task_no=arg_parser.task_no))

    _consumer(log=log)
    log.info('End task')


if __name__ == '__main__':
    main()
