# -*- coding: utf-8 -*-

import argparse
from datetime import datetime, timedelta
from dataclasses import asdict
from typing import List
import uuid

import const
import logger
from mq import MQ, MQMsgData
import auapi


def _send_msg(send_data: MQMsgData,
              queue_name: str,
              routing_key: str,
              log: logger.Logger):
    try:
        with MQ(**const.MQ_CONNECT,
                queue=queue_name,
                routing_key=routing_key) as queue:
            msg = asdict(send_data)
            queue.send_message(message=msg)
            log.info('Send message queue={queue}, data={data}'.format(queue=queue_name, data=msg))
    except Exception:
        log.exception('Failed to send mq message error')
        raise


def _get_order_item_id_list(log: logger.Logger) -> List[str]:
    end_time = datetime.now()
    start_time = end_time - timedelta(days=const.ORDER_LIST_GET_LAST_DAYS)

    with auapi.AuAPI(log=log) as api:
        orders = api.trade.search(start_time=start_time, end_time=end_time)

        item_ids = []
        for order in orders:
            for detail in order.details:
                item_ids.append(detail.item_code)

    log.info('Get order list: order_list={order_list}'.format(order_list=item_ids))
    return item_ids


def _producer(log: logger.Logger):
    item_ids = _get_order_item_id_list(log=log)
    if not item_ids:
        return

    send_data = MQMsgData(id=str(uuid.uuid4()),
                          item_ids=item_ids,
                          msg_send_time=datetime.now().isoformat())
    log.info('Send MQ')
    # Yahoo!ショッピング
    _send_msg(send_data=send_data,
              queue_name=const.MQ_YSHOP_QUEUE,
              routing_key=const.MQ_YSHOP_ROUTING_KEY,
              log=log)
    # 楽天
    _send_msg(send_data=send_data,
              queue_name=const.MQ_RAKUTEN_QUEUE,
              routing_key=const.MQ_RAKUTEN_ROUTING_KEY,
              log=log)


def main():
    parser = argparse.ArgumentParser(description='stockout_au_producer')
    parser.add_argument('--task_no',
                        required=True,
                        type=int,
                        help='input process No type integer')

    arg_parser = parser.parse_args()
    log = logger.Logger(task_name='stockout-au-producer',
                        sub_name='main',
                        name_datetime=datetime.now(),
                        task_no=arg_parser.task_no,
                        **const.LOG_SETTING)
    log.info('Start task')
    log.info('Input args task_no={task_no}'.format(task_no=arg_parser.task_no))

    _producer(log=log)
    log.info('End task')


if __name__ == '__main__':
    main()
