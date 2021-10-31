# -*- coding: utf-8 -*-

import argparse
from datetime import datetime
from typing import Dict
import functools

import const
import logger
from mq import MQ, MQMsgData
import rapi


def _stockout(msg_data: MQMsgData, log: logger.Logger):
    item_ids = msg_data.item_ids
    with rapi.RakutenAPI(log=log) as api:
        try:
            inventories = api.inventory.get(item_urls=item_ids)
        except Exception:
            raise Exception('stockout error')

        set_list = []
        for inventory_data in inventories:
            if inventory_data.inventory_count > 0:
                set_data = rapi.InventoryUpdateData(item_url=inventory_data.item_url,
                                                    inventory_count=0)
                set_list.append(set_data)

        if set_list:
            try:
                result = api.inventory.update(update_items=set_list)
            except Exception:
                log.exception('Failed to update stock')
                raise Exception('stockout error')
            log.info('Update stock data={data}'.format(data=set_list))
            log.info('update stock error data={data}'.format(data=result))
            return

        log.info('NA update stock data')


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
                queue=const.MQ_RAKUTEN_QUEUE,
                routing_key=const.MQ_RAKUTEN_ROUTING_KEY) as queue:
            queue.open()
            callback = functools.partial(_relist_on_message, log=log)
            queue.receive_message(callback)

    except Exception:
        log.exception('Failed to MQ connect')
        raise


def main():
    parser = argparse.ArgumentParser(description='stockout_rakuten_consumer')
    parser.add_argument('--task_no',
                        required=True,
                        type=int,
                        help='input process No type integer')

    arg_parser = parser.parse_args()
    log = logger.Logger(task_name='stockout-rakuten-consumer',
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
