# -*- coding: utf-8 -*-
import datetime
import json
import math
import multiprocessing
import os
import pickle
import random
import re
import requests
import sys
import time
import base64
import urllib.request
from pytz import timezone
import xml.etree.ElementTree as ET
from decimal import Decimal, ROUND_HALF_UP
from logging import Formatter, getLogger, StreamHandler, DEBUG
from logging.handlers import RotatingFileHandler
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.support.select import Select
import os.path

from datetime import datetime as dt
from collections import OrderedDict
import pprint
from time import sleep
from selenium.common.exceptions import TimeoutException
import urllib.error
from urllib.parse import quote
import lxml

_dir = os.path.dirname(os.path.abspath(__file__))

# 各種API設定------------------------------------------------------------
buysetting_json = open('config/setting.json', 'r', encoding="utf-8_sig")
buy_setting = json.load(buysetting_json)

# 楽天
serviceSecret = b""
licenseKey = buy_setting["RMS_API_licensekey"].encode("UTF-8")

# wowma
w_licenseKey = buy_setting["AU_API_key"].encode("UTF-8")
w_headers = {
    'method': 'POST',
    'Authorization': b"Bearer " + w_licenseKey,
    'Content-Type': 'application/x-www-form-urlencoded'
}
w_headers2 = {
    'method': 'GET',
    'Authorization': b"Bearer " + w_licenseKey,
    'Content-Type': 'application/xml; charset=utf-8'
}

# yahoo_shop
token_json = open('config/yahoo_token.json', 'r', encoding="utf-8_sig")
token_seting = json.load(token_json)

# データセット
APPID = buy_setting["YAHOO_APPID"]
SECRET = buy_setting["YAHOO_SECRET"]
CALLBACK_URL = 'https://www.ganbare-tencho.net/auth/callback.php'
TOKEN_URL = 'https://auth.login.yahoo.co.jp/yconnect/v1/token'
tmp = APPID + ':' + SECRET

client_id = buy_setting["YAHOO_APPID"]  # クライアントID
client_secret = buy_setting["YAHOO_SECRET"]  # クライアントシークレット
callback_url = 'http://playerinc.jp/auth/callback.php'  # コールバックURL
auth_base_url = 'https://auth.login.yahoo.co.jp'
token_url = auth_base_url + '/yconnect/v1/token'
login_base_url = 'https://login.yahoo.co.jp/config/login'
account_edit_url = 'https://account.edit.yahoo.co.jp'
nonce = random.randrange(10 ** 31, 10 ** 32)
base64_id_secret = client_id + ':' + client_secret
base64_id_secret_byte = base64.b64encode(base64_id_secret.encode('utf-8'))
auth_header = 'Basic ' + base64_id_secret_byte.decode('ascii')
user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.100 Safari/537.36'
http_version = 'HTTP/1.1'
content_type = 'application/x-www-form-urlencoded; charset=utf-8'
user_name = buy_setting["YAHOO_user_name"]  # メールアドレス
passwd = buy_setting["YAHOO_passwd"]  # パスワード
default_cookie = ''
yjbfp_items = ''


def init_driver(id):
    logger = getMyLogger(id)

    options = Options()
    options.add_argument('--headless')
    options.add_argument('--blink-settings=imagesEnabled=false')
    driver = None
    counter = 0
    while driver is None:
        counter += 1
        try:
            driver = webdriver.Chrome(chrome_options=options, service_args=["hide_console"])
        except Exception as e:
            logger.exception(e)
            if counter >= 10:
                raise
            time.sleep(10)
    driver.implicitly_wait(30)
    driver.set_page_load_timeout(300)
    driver.set_script_timeout(300)
    return driver


def load_cookie(driver, id):
    logger = getMyLogger(id)

    logger.debug(id + ':go to top page.')
    for i in range(100):
        try:
            driver.get("https://auctions.yahoo.co.jp")
            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, '//*[@id="ygmhlog"]')))
            break
        except Exception as e:
            logger.debug(id + ':top page timeout.')

            # ChromeDriverを作り直す
            driver.quit()
            time.sleep(10)
            driver = init_driver(id)

    logger.debug(id + ':load cookie.')
    path = 'cookie/' + id + '.cookie'
    if not os.path.isfile(path):
        # クッキーファイルがなければ終了
        logger.info(id + ':cookie not exists.')
        driver.close()
        driver.quit()
        return False
    with open(path, 'rb') as f:
        cookies = pickle.load(f)

    for c in cookies:
        if c['domain'] != '.yahoo.co.jp':
            continue
        if 'expiry' in c:
            del c['expiry']
        driver.add_cookie(c)

    return True


def getMyLogger(id):
    # ロギング設定
    logger = getLogger(__name__)
    if not logger.handlers:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        formatter = Formatter('%(asctime)s:%(message)s')
        fileHandler = RotatingFileHandler(r'logs/stockout' + id + '.log', 'a', 1048576, 1)
        fileHandler.setLevel(DEBUG)
        fileHandler.setFormatter(formatter)
        streamHandler = StreamHandler()
        streamHandler.setLevel(DEBUG)
        streamHandler.setFormatter(formatter)
        logger.setLevel(DEBUG)
        logger.addHandler(fileHandler)
        logger.addHandler(streamHandler)

    return logger


def get_az_code():
    url = auth_base_url + '/yconnect/v1/authorization?response_type=code&client_id=' + client_id + '&redirect_uri=' + callback_url + '&scope=openid+profile&nonce=' + str(
        nonce)
    driver = init_driver('auth')
    driver.get(url)
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.NAME, 'login')))
    time.sleep(1)
    driver.find_element_by_name('login').send_keys(user_name)
    driver.find_element_by_name('btnNext').click()
    WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.NAME, 'passwd')))
    time.sleep(1)
    previous_url = driver.current_url
    driver.find_element_by_name("passwd").click()
    driver.find_element_by_name("passwd").send_keys(passwd)
    driver.find_element_by_name('btnSubmit').click()
    previous_url = driver.current_url
    try:
        WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, '//*[@id=".save"]')))
        previous_url = driver.current_url
        driver.find_element_by_xpath('//*[@id=".save"]').click()
    except:
        pass

    time.sleep(1)
    az_code = driver.current_url
    code_str = '?code='
    code_idx = driver.current_url.find(code_str)
    az_code = driver.current_url[code_idx + 6:code_idx + 14]
    # az_code = 'kupdybw5'

    driver.quit()

    return az_code


def get_access_token(http_version, content_type, auth_header, callback_url, az_code):
    headers = {
        'HTTP-Version': http_version,
        'Content-Type': content_type,
        'Authorization': auth_header
    }

    data = {
        'grant_type': 'authorization_code',
        'code': az_code,
        'redirect_uri': callback_url
    }

    response = requests.post(token_url, data=data, headers=headers)
    # print(response.text)
    access_token = response.json()['access_token']
    refresh_token = response.json()['refresh_token']

    return access_token, refresh_token


def update_access_token(refresh_token):
    headers = {
        'HTTP-Version': http_version,
        'Content-Type': content_type,
        'Authorization': auth_header
    }

    data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
    }

    response = requests.post(token_url, data=data, headers=headers)
    u_access_token = response.json()['access_token']

    return u_access_token


def change_item_status(account, now1, now2):
    login_id = account['login_id']
    logger = getMyLogger(login_id)

    try:
        driver = init_driver(login_id)

        # 最初にランダムなディレイを置いて同時アクセスを避ける
        time.sleep(random.randint(1, 30))

        if not load_cookie(driver, login_id):
            return

        for i in range(100):
            try:
                logger.debug(login_id + ':try to load list page.')
                previous_url = driver.current_url
                driver.get('https://onavi.auctions.yahoo.co.jp/onavi/show/storelist?select=closed&haswinner=1')

                WebDriverWait(driver, 30).until(lambda driver: driver.current_url != previous_url)
                # 出品終了落札者なし商品数が取得できるまで待つ
                WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH,
                                                                                '/html/body/center/center[6]/table/tbody/tr/td/center[2]/table/tbody/tr/td/table/tbody/tr[3]/td/table/tbody/tr[2]/td[2]/small')))
                logger.debug(login_id + ':list page loaded.')
                break;
            except Exception as e:
                try:
                    # 終了したオークションはありませんメッセージがあれば離脱
                    driver.find_element_by_xpath(
                        '//*[@id="acWrContents"]/div/table[1]/tbody/tr/td/table/tbody/tr[2]/td/center')
                    logger.debug(login_id + ':table not found.')
                    break
                except Exception as e:
                    pass
                logger.debug(login_id + ':list page timeout.')

                # ChromeDriverを作り直す
                driver.quit()
                time.sleep(10)
                driver = init_driver(login_id)
                if not load_cookie(driver, login_id):
                    return

        logger.debug(login_id + ':get page source.')
        bs4 = BeautifulSoup(driver.page_source, "html5lib")
        logger.debug(login_id + ':process with bs4.')
        table = bs4.find("table", attrs={"bgcolor": "#dcdcdc"}, align="center")
        table = bs4('table')[32]

        auction_ids = []
        before_prices = {}
        pre_end_times = {}
        control_no = {}
        access_count = {}
        reports = []
        list_data = []
        cnt = 1
        cnt_end = 5
        end_flg = 0

        # テーブルがない場合は、落札者なし出品終了が0件か、ログインできていないので終了
        # テーブルなし判定は終了オークションなしメッセージの時点で済んでいるので二重判定だがよしとする
        if table is not None:
            # 落札者なし出品終了件数取得
            element = driver.find_element_by_xpath(
                '/html/body/center/center[6]/table/tbody/tr/td/table[6]/tbody/tr/td/table/tbody/tr/td[1]/small/b[3]')
            product_count = element.text.strip()

            rows = table.findAll("tr")

            # ヘッダ行を削除する
            rows.pop(0)

            for row in rows:

                cells = row.findAll('td')

                if len(cells) >= 6:
                    if cells[9].get_text().strip() == '終了時間':
                        continue

                        # 終了日を取得
                    dt = datetime.datetime.strptime(cells[9].get_text().strip(), '%m月%d日 %H時%M分')

                    if now1.month == dt.month and now1.day == dt.day:
                        # 取得処理
                        tmp = [cells[2].get_text().strip(), cells[9].get_text().strip()]
                        list_data.append(tmp)
                        pass
                    elif now2.month == dt.month and now2.day == dt.day:
                        # 取得処理
                        tmp = [cells[2].get_text().strip(), cells[9].get_text().strip()]
                        list_data.append(tmp)
                        pass
                    else:
                        continue

            # 落札者なし出品終了件数 / 50 を繰り上げたページ数まで読み取る
            for i in range(2, (math.ceil(int(product_count) / 50) + 1)):
                if end_flg == 1:
                    break
                for j in range(100):
                    if end_flg == 1:
                        break
                    try:
                        previous_url = driver.current_url
                        driver.get(
                            'https://onavi.auctions.yahoo.co.jp/onavi/show/storelist?select=closed&haswinner=1&page=' + str(
                                i))
                        WebDriverWait(driver, 30).until(lambda driver: driver.current_url != previous_url)
                        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH,
                                                                                        '/html/body/center/center[6]/table/tbody/tr/td/center[2]/table/tbody/tr/td/table/tbody/tr[3]/td/table')))
                        bs4 = BeautifulSoup(driver.page_source, "html5lib")
                        # table = bs4.find("table", attrs={"bgcolor": "#dcdcdc"})
                        table = bs4('table')[32]
                        if table is None:
                            break
                        rows = table.findAll("tr")
                        # ヘッダ行を削除する
                        rows.pop(0)
                        for row in rows:
                            cells = row.findAll('td')
                            if len(cells) >= 6:
                                if cells[9].get_text().strip() == '終了時間':
                                    continue

                            # 終了日を取得
                            dt = datetime.datetime.strptime(cells[9].get_text().strip(), '%m月%d日 %H時%M分')

                            if now1.month == dt.month and now1.day == dt.day:
                                # 取得処理
                                tmp = [cells[2].get_text().strip(), cells[9].get_text().strip()]
                                list_data.append(tmp)
                                pass
                            elif now2.month == dt.month and now2.day == dt.day:
                                # 取得処理
                                tmp = [cells[2].get_text().strip(), cells[9].get_text().strip()]
                                list_data.append(tmp)
                                pass
                            else:
                                end_flg = 1
                                break

                        break

                    except Exception as e:
                        logger.debug(login_id + ':list page timeout.')

                        # ChromeDriverを作り直す
                        driver.quit()
                        time.sleep(10)
                        driver = init_driver(login_id)
                        if not load_cookie(driver, login_id):
                            return
        else:
            logger.debug(login_id + ':table not found.')
    except Exception as e:
        logger.debug(login_id + ':exception occurred on read target list.')
        logger.exception(e)

    return list_data


# Yahooショッピング在庫OFF
def y_stock_out(http_version, content_type, auth_header, callback_url, access_token, control_no):
    auth = 'Bearer ' + access_token
    headers = {
        'HTTP-Version': 'http_version',
        'Content-Type': content_type,
        'Authorization': auth
    }

    api_data = "seller_id=&item_code=" + str(control_no) + "&quantity=" + "0"

    API_url = "https://circus.shopping.yahooapis.jp/ShoppingWebService/V1/setStock"
    response = requests.post(API_url, data=api_data, headers=headers)
    logger.info('Yahoo Stockout:' + control_no)
    return response


# wowma
def w_stock_out(control_no):
    url = 'https://api.manager.wowma.jp/wmshopapi/updateStock'
    xml = """
    <request>
    <shopId></shopId>
    <stockUpdateItem>
    <itemCode>""" + str(control_no) + """</itemCode>
    <stockSegment>1</stockSegment>
    <stockCount>0</stockCount>
    </stockUpdateItem>
    </request>
    """
    bytesXMLPostBody = xml.encode("UTF-8")
    # r = requests.post(url, params=xml, headers=headers2)
    req = urllib.request.Request(url=url, data=bytesXMLPostBody, headers=w_headers2)

    try:
        with urllib.request.urlopen(req) as response:
            response_body = response.read().decode("utf-8")
            soup = BeautifulSoup(response_body, "lxml")
            print(soup)
    except urllib.error.HTTPError as err:
        soup = BeautifulSoup(err, "lxml")
        print(soup)
    logger.info('Wowma Stockout:' + control_no)


# rakuten
def r_stock_out(control_no):
    headers = {'Authorization': b"ESA " + base64.b64encode(serviceSecret + b':' + licenseKey)}
    xml = """
        <?xml version="1.0" encoding="UTF-8"?>
        <request>
        <itemUpdateRequest>
            <item>
                <itemUrl>""" + str(control_no) + """</itemUrl>
                <itemInventory>
                    <inventoryType>1</inventoryType>
                    <inventories>
                        <inventory>
                            <inventoryCount>1</inventoryCount>
                        </inventory>
                    </inventories>
                </itemInventory>
            </item>
        </itemUpdateRequest>
        </request>
        """

    url = 'https://api.rms.rakuten.co.jp/es/1.0/item/update'

    # 楽天商品あり・API実行ログ
    # logger.debug(auction_id + ':RMS API START.')

    r = requests.post(url, data=xml, headers=headers)
    if str(r) == "<Response [200]>":
        # 楽天API成功ログ
        # logger.debug(auction_id + ':RMS API complete.')
        print('success')

    else:
        # 楽天API失敗ログ
        # logger.debug(auction_id + ':RMS API NG.')
        # logger.exception(r)
        # logger.exception(r.text)
        print('failed')
    logger.info('RMS Stockout:' + control_no)


# 楽天販売リスト取得
def r_get_order_list():
    headers = {
        'Authorization': b"ESA " + base64.b64encode(serviceSecret + b':' + licenseKey),
        'Content-Type': 'application/json; charset=utf-8',
    }
    # ■■■■■■■■　post　■■■■■■■■■■
    # 現在時から何時間前を設定（63日以内制限あり）
    int_st = -48  # 24H前を想定

    # 開始日時:jst_st 終了日時:jst_ed を生成
    # たぶんもっとスマートな生成方法があるはず
    jst_st = datetime.datetime.now(timezone('Asia/Tokyo')) + datetime.timedelta(hours=int_st)
    jst_st = "{0:%Y-%m-%dT%H:%M:%S}".format(jst_st)
    jst_st = str(jst_st) + "+0900"

    jst_ed = datetime.datetime.now(timezone('Asia/Tokyo'))
    jst_ed = "{0:%Y-%m-%dT%H:%M:%S}".format(jst_ed)
    jst_ed = str(jst_ed) + "+0900"

    # post文字列生成
    url = 'https://api.rms.rakuten.co.jp/es/2.0/order/searchOrder/'
    data = {
        "dateType": 1,
        "startDatetime": jst_st,
        "endDatetime": jst_ed,
        "PaginationRequestModel":
            {
                "requestRecordsAmount": 1000,
                "requestPage": 1,
                "SortModelList": [
                    {
                        "sortColumn": 1,
                        "sortDirection": 1
                    }
                ]
            }
    }

    # post
    req = urllib.request.Request(url, json.dumps(data).encode(), headers)
    with urllib.request.urlopen(req) as res:
        body = res.read()

    # APIの戻り値を格納
    json_load = json.loads(body)
    order_list = json_load['orderNumberList']

    # print(jst_st)
    # print(jst_ed)

    # 販売リストから販売商品情報を取得
    # get_order(json_load['orderNumberList'],headers)
    item_list = []
    # post文字列生成
    url = 'https://api.rms.rakuten.co.jp/es/2.0/order/getOrder/'
    data = {
        "orderNumberList": order_list
    }
    # post
    req = urllib.request.Request(url, json.dumps(data).encode(), headers)
    with urllib.request.urlopen(req) as res:
        body = res.read()

    # APIの戻り値を格納
    json_load = json.loads(body)
    for i in json_load['OrderModelList']:
        PackageModelList = i['PackageModelList']
        for p in PackageModelList:
            ItemModelList = p['ItemModelList']
            for item in ItemModelList:
                item_list.append(item['manageNumber'])
    return item_list


# wowma販売リスト取得
def w_get_order_list(e_date, s_date):
    w_data = []
    # テスト用にスタート位置手動設定
    tmp = s_date
    s_date = '2020/12/01'  # >>検証後削除
    # **********************************

    url = 'https://api.manager.wowma.jp/wmshopapi/searchTradeInfoListProc?' + "shopId=56356822&totalCount=1000" + "&startDate=" + str(
        s_date).replace("-", "/") + "&endDate=" + str(e_date).replace("-", "/")
    r = requests.get(url, params="", headers=w_headers)

    s_date = tmp

    # レスポンスデータから商品情報取得
    XmlData = r.text
    root = ET.fromstring(XmlData)

    # # 対象件数
    cnt = 0
    cnt = int(root[1].text)

    for i in range(cnt):
        # print(root[i].tag)
        if root[2 + i].tag != 'orderInfo':
            continue
        # orderInfoのみ処理
        # 販売日を取得
        tdatetime = datetime.datetime.strptime(root[2 + i][0].text, '%Y/%m/%d %H:%M')
        tdatetime = datetime.date(tdatetime.year, tdatetime.month, tdatetime.day)

        w_sell_date = tdatetime.strftime('%Y/%m/%d')

        # 販売日が機能の日付よりも前の場合は処理をストップ
        # if s_date > tdatetime:
        #    continue

        # 商品数取得
        item_cnt = 0
        for p in root[2 + i]:

            if p.tag == 'detail':
                item_cnt = item_cnt + 1

        # 商品コードを販売商品分取得
        for q in range(item_cnt):
            w_itemcode = root[2 + i][33 + q][2].text
            w_data.append(w_itemcode)

    return w_data


# Yahooショッピング販売リスト取得
def get_sell_list(http_version, content_type, auth_header, callback_url, access_token, s_date, e_date):
    auth = 'Bearer ' + access_token
    user = 'Yahoo AppID: ' + APPID
    headers = {
        'HTTP-Version': 'http_version',
        'Authorization': auth,
        'Host': 'circus.shopping.yahooapis.jp'
    }

    xml = """
    <Req>
    <Search>
    <Result>2000</Result>
    <Condition>
        <OrderTimeFrom>""" + str(s_date) + """</OrderTimeFrom>
        <OrderTimeTo>""" + str(e_date) + """</OrderTimeTo>
    </Condition>
    <Field>OrderId,OrderTime</Field>
    </Search>
    <SellerId>fukuwauchi-player</SellerId>
    </Req>
    """

    API_url = "https://circus.shopping.yahooapis.jp/ShoppingWebService/V1/orderList"
    bytesXMLPostBody = xml.encode("UTF-8")
    response = requests.post(API_url, data=xml, headers=headers)

    # レスポンスデータから商品情報取得
    XmlData = response.text
    root = ET.fromstring(XmlData)
    order_list = []
    item_list = []
    for child in root[1]:
        if child.tag != 'OrderInfo':
            continue
        for child2 in child:
            # print(child2.tag,child2.text)
            # get order id
            if child2.tag == 'OrderId':
                order_list.append(child2.text)

    # OrderId>>itemcode
    for order in order_list:
        xml = """
        <Req>
        <Target>
            <OrderId>""" + str(order) + """</OrderId>
            <Field>OrderId,ItemId</Field>
        </Target>
        <SellerId>parisparis</SellerId>
        </Req>
        """

        API_url = "https://circus.shopping.yahooapis.jp/ShoppingWebService/V1/orderInfo"
        bytesXMLPostBody = xml.encode("UTF-8")
        response = requests.post(API_url, data=xml, headers=headers)
        # レスポンスデータから商品情報取得
        XmlData = response.text
        root = ET.fromstring(XmlData)

        for child in root[0][1]:
            if child.tag != 'Item':
                continue
            item_list.append(child[0].text)

    return item_list


def yo_stock_out(account, y_sell_list):
    login_id = account['login_id']
    logger = getMyLogger(login_id)

    try:
        driver = init_driver(login_id)

        # 最初にランダムなディレイを置いて同時アクセスを避ける
        time.sleep(random.randint(1, 30))

        if not load_cookie(driver, login_id):
            return

        for i in range(100):
            try:
                logger.debug(login_id + ':try to load list page.')
                previous_url = driver.current_url
                driver.get('https://onavi.auctions.yahoo.co.jp/onavi/show/storelist?select=closed&haswinner=1')

                WebDriverWait(driver, 30).until(lambda driver: driver.current_url != previous_url)
                # 出品終了落札者なし商品数が取得できるまで待つ
                WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH,
                                                                                '/html/body/center/center[6]/table/tbody/tr/td/center[2]/table/tbody/tr/td/table/tbody/tr[3]/td/table/tbody/tr[2]/td[2]/small')))
                logger.debug(login_id + ':list page loaded.')
                break;
            except Exception as e:
                try:
                    # 終了したオークションはありませんメッセージがあれば離脱
                    driver.find_element_by_xpath(
                        '//*[@id="acWrContents"]/div/table[1]/tbody/tr/td/table/tbody/tr[2]/td/center')
                    logger.debug(login_id + ':table not found.')
                    break
                except Exception as e:
                    pass
                logger.debug(login_id + ':list page timeout.')

                # ChromeDriverを作り直す
                driver.quit()
                time.sleep(10)
                driver = init_driver(login_id)
                if not load_cookie(driver, login_id):
                    return

        # ヤフオク出品取り下げ処理
        for sell in y_sell_list:
            driver.get('https://auctions.yahoo.co.jp/sellertool/sellings?select=business_commodity_id&q=' + str(sell))
            print(str(sell))

            element = driver.find_elements_by_xpath('//*[@id="pageTop"]/div[3]/div[2]/div/div[4]/div/div[1]/span')

            # 対象商品があるか確認
            if len(element) == 0:
                print(str(sell) + ':none')
                continue

            # オークションID取得
            auc_id = driver.find_element_by_xpath('//*[@id="checkArea"]/ul/li[2]/p[2]').text[9:]

            # 出品取り下げ処理
            previous_url = driver.current_url
            driver.get('https://page.auctions.yahoo.co.jp/jp/show/cancelauction?aID=' + str(auc_id))
            WebDriverWait(driver, 30).until(lambda driver: driver.current_url != previous_url)
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, '/html/body/center[1]/form/table/tbody/tr[3]/td/input')))
            previous_url = driver.current_url
            driver.find_element_by_xpath('/html/body/center[1]/form/table/tbody/tr[3]/td/input').click()
            WebDriverWait(driver, 30).until(lambda driver: driver.current_url != previous_url)

            # 終了済みページで出品削除処理
            previous_url = driver.current_url
            driver.get('https://onavi.auctions.yahoo.co.jp/onavi/show/storelist?select=closed')
            WebDriverWait(driver, 30).until(lambda driver: driver.current_url != previous_url)
            driver.find_element_by_xpath('//*[@id="f_merchant_item_id"]').send_keys(str(sell))
            driver.find_element_by_xpath('//*[@id="search_action_button"]/table/tbody/tr/td[2]/small/input[1]').click()
            element = driver.find_element_by_xpath(
                '/html/body/center/center[6]/table/tbody/tr/td/center[2]/table/tbody/tr/td/table/tbody/tr[3]/td/table/tbody/tr[2]/td[2]/small').text

            if element == auc_id:
                driver.find_element_by_xpath(
                    '/html/body/center/center[6]/table/tbody/tr/td/center[2]/table/tbody/tr/td/table/tbody/tr[3]/td/table/tbody/tr[2]/td[1]/input[1]').click()
                time.sleep(0.3)
                driver.find_element_by_xpath(
                    '/html/body/center/center[6]/table/tbody/tr/td/center[2]/table/tbody/tr/td/table/tbody/tr[1]/td/table/tbody/tr/td/small/input[2]').click()
                previous_url = driver.current_url
                driver.find_element_by_xpath(
                    '/html/body/center/center[5]/table/tbody/tr/td/table[3]/tbody/tr/td/small/input[1]').click()
                WebDriverWait(driver, 30).until(lambda driver: driver.current_url != previous_url)
                logger.info('Yahuoku Stockout:' + str(sell))

    except Exception as e:
        logger.debug(login_id + ':exception occurred on read target list.')
        logger.exception(e)


if __name__ == '__main__':

    logger = getMyLogger('main')

    logger.info('')
    logger.info('stockout start.')

    y_sell_list = []

    try:
        # PS(光回線)のヤフオクアカウント情報取得
        api_url = "http://playerinc07.xsrv.jp/api/auctionAccounts/1"
        res = None
        for j in range(120):
            try:
                res = requests.post(api_url, auth=('', ''))
                break
            except Exception as e:
                logger.exception(e)
                time.sleep(60)
        if res is None:
            accounts = []
        else:
            accounts = res.json()
        # 処理対象のグループのみを抽出(引数は98)
        tmp = []
        for account in accounts:
            if (account['AuctionAccount']['group'] == '98') or ('98' == '0'):
                tmp.append(account['AuctionAccount'])
        accounts = tmp
        dt = datetime.datetime.now()
        now1 = datetime.date(dt.year, dt.month, dt.day)
        now2 = datetime.date(dt.year, dt.month, dt.day - 1)

        # Yahoo APIの認証情報取得
        az_code = get_az_code()

        let = get_access_token(http_version, content_type, auth_header, callback_url, az_code)
        access_token = let[0]
        refresh_token = let[1]

        # ヤフオク販売済商品リスト取得
        sell_list = []
        for account in accounts:
            tmp = change_item_status(account, now1, now2)
            for p in tmp:
                sell_list.append(p)

        # ヤフオク在庫反映
        access_token = update_access_token(refresh_token)
        for sell in sell_list:
            control_no = sell[0]
            logger.info('Yahuoku sell:' + control_no)
            # ヤフーショッピング
            y_stock_out(http_version, content_type, auth_header, callback_url, access_token, control_no)
            # wowma
            w_stock_out(control_no)
            # RMS
            r_stock_out(control_no)

        # 楽天販売済商品リスト取得
        r_sell_list = []
        r_sell_list = r_get_order_list()

        # 楽天在庫反映
        access_token = update_access_token(refresh_token)
        for sell in r_sell_list:
            control_no = sell
            logger.info('RMS sell:' + control_no)
            y_sell_list.append(control_no)
            # ヤフーショッピング
            y_stock_out(http_version, content_type, auth_header, callback_url, access_token, control_no)
            # wowma
            w_stock_out(control_no)

        # wowma販売済商品リスト取得
        w_sell_list = []
        w_sell_list = w_get_order_list(now1, now2)

        # wowma在庫反映
        access_token = update_access_token(refresh_token)
        for sell in w_sell_list:
            control_no = sell
            logger.info('Wowma sell:' + control_no)
            y_sell_list.append(control_no)
            # ヤフーショッピング
            y_stock_out(http_version, content_type, auth_header, callback_url, access_token, control_no)
            # RMS
            r_stock_out(control_no)

        # ヤフーショッピング販売済商品リスト取得
        access_token = update_access_token(refresh_token)
        ys_sell_list = []
        ys_sell_list = get_sell_list(http_version, content_type, auth_header, callback_url, access_token,
                                     str(now2).replace('-', '') + '000000', str(now1).replace('-', '') + '000000')

        # ヤフーショッピング在庫反映
        access_token = update_access_token(refresh_token)
        for sell in ys_sell_list:
            control_no = sell
            y_sell_list.append(control_no)
            logger.info('Yahoo sell:' + control_no)
            # RMS
            r_stock_out(control_no)
            # wowma
            w_stock_out(control_no)

        # ヤフオク在庫更新
        # 各ショップで販売された商品管理番号のリストをもとに出品取り下げ処理
        for account in accounts:
            yo_stock_out(account, y_sell_list)


    except Exception as e:
        logger.exception(e)

    logger.info('stckout end.')
    logger.info('')
