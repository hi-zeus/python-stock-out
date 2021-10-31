# -*- coding: utf-8 -*-

import os
import argparse
from datetime import datetime, timedelta
from dataclasses import asdict
from typing import List
import uuid

import const
import logger
from mq import MQ, MQMsgData
import ysapi


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


def _get_order_item_id_list(task_no: int, log: logger.Logger) -> List[str]:
    log.info('Start get order list')
    end_time = datetime.now()
    start_time = end_time - timedelta(days=const.ORDER_LIST_GET_LAST_DAYS)

    profile_dirname = 'yshop_producer_{task_no}'.format(task_no=task_no)
    profile_dir = os.path.join(const.CHROME_PROFILE_DIR, profile_dirname)
    auth_file = os.path.join(const.TMP_DIR, 'yshop_auth_producer_{task_no}.json').format(task_no=task_no)
    with ysapi.YahooAPI(profile_dir=profile_dir,
                        log=log,
                        application_id=const.YJDN_APP_ID_PRODUCER,
                        secret=const.YJDN_SECRET_PRODUCER,
                        auth_file=auth_file,
                        business_id=const.YSHOP_BUSINESS_ID,
                        business_password=const.YSHOP_BUSINESS_ID,
                        yahoo_id=const.YSHOP_YAHOO_ID,
                        yahoo_password=const.YSHOP_YAHOO_PASSWORD) as api:
        log.info('update token')
        api.auth.update_token()
        order_list = api.shopping.order.list.get(order_time_from=start_time, order_time_to=end_time)

        item_ids = []
        for order_list_data in order_list:
            order_id = order_list_data.order_id
            order_info_list = api.shopping.order.info.get(order_id=order_id)

            for order_info in order_info_list:
                item_id = order_info.item_id
                item_ids.append(item_id)

    log.info('Get order list: order_list={order_list}'.format(order_list=item_ids))
    return item_ids


def _producer(task_no: int, log: logger.Logger):
    item_ids = _get_order_item_id_list(task_no=task_no, log=log)
    if not item_ids:
        return

    send_data = MQMsgData(id=str(uuid.uuid4()),
                          item_ids=item_ids,
                          msg_send_time=datetime.now().isoformat())
    log.info('Send MQ')
    # 楽天
    _send_msg(send_data=send_data,
              queue_name=const.MQ_RAKUTEN_QUEUE,
              routing_key=const.MQ_RAKUTEN_ROUTING_KEY,
              log=log)
    # AuPayマーケット
    _send_msg(send_data=send_data,
              queue_name=const.MQ_AU_QUEUE,
              routing_key=const.MQ_AU_ROUTING_KEY,
              log=log)


def main():
    parser = argparse.ArgumentParser(description='stockout_yshop_producer')
    parser.add_argument('--task_no',
                        required=True,
                        type=int,
                        help='input process No type integer')

    arg_parser = parser.parse_args()
    log = logger.Logger(task_name='stockout-yshop-producer',
                        sub_name='main',
                        name_datetime=datetime.now(),
                        task_no=arg_parser.task_no,
                        **const.LOG_SETTING)
    log.info('Start task')
    log.info('Input args task_no={task_no}'.format(task_no=arg_parser.task_no))

    _producer(task_no=arg_parser.task_no, log=log)
    log.info('End task')


if __name__ == '__main__':
    main()
