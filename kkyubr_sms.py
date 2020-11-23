
# -*- coding: utf-8 -*-
'''
phps.sms
~~~~~~~~~~~~
This module send sms to Phps.
:copyright: (c) 2020 by kkyubrother.
:license: Apache2, see LICENSE for more details.
:original: www.phps.kr
'''

from collections import namedtuple
import datetime
import re
import os

import requests
from phpserialize import loads

IP_CHECK_URL    = 'https://api.ipify.org'
SERVER_URL      = 'https://sms.phps.kr/lib/send.sms'
SERVER_ENCODING = 'euc-kr'

Data = namedtuple('Data', 'tr_to tr_txtmsg')
__pattern_num   = re.compile(r'010[- ]?\d{4}[- ]?\d{4}')
__ENV_IP        = os.environ.get('REMOTE_ADDR')


class SMSError(Exception):
    text = None

    def __init__(self, text: str):
        self.text = text


def _parse_response(content: bytes) -> dict:
    r = dict()
    for k, v in loads(content).items():
        try:
            k = k.decode('utf-8')
        except AttributeError:
            pass
        try:
            v = v.decode('utf-8')
        except AttributeError:
            pass
        r[k] = v
    return r


def _get_my_ip() -> str:
    return __ENV_IP if __ENV_IP else requests.get(IP_CHECK_URL).text


def _check_tr_to(tr_to: str) -> str:
    tr_to = tr_to.strip()
    if not __pattern_num.match(tr_to):
        raise SMSError("tr_to is wrong.")
    return tr_to


def _slice_tr_txtmsg(tr_txtmsg: str) -> list:
    txt_list = list(tr_txtmsg)
    temp_sliced = list()
    popped = list()

    while txt_list:
        popped.append(txt_list.pop(0))

        if len(popped) > 44:
            t = ''.join(popped)
            e = t.encode(SERVER_ENCODING)
            l = len(e)
            if l == 89 or l == 90:
                temp_sliced.append(e)
                popped.clear()

    if popped:
        temp_sliced.append((''.join(popped)).encode(SERVER_ENCODING))

    return temp_sliced


class SMS():
    __tr_id     = None
    __tr_key    = None
    __tr_from   = None
    __data      = None


    def __init__(self, tr_id: str, tr_key:str, tr_from:str):
        self.__tr_id    = tr_id
        self.__tr_key   = tr_key
        self.__tr_from  = tr_from
        self.__data     = list()

    def add(self, tr_to, tr_txtmsg, auto_slice: bool=False):
        '''Add message | 메시지를 추가한다

        :tr_to: phone number | 수신자 전화번호
        :tr_txtmsg: text message | 수신자 메시지
        :auto_slice: Automatically cut and send over-length messages | 길이 초과 메시지를 자동으로 잘라 보내기

        '''
        tr_to = _check_tr_to(tr_to=tr_to)

        txt_bytes = tr_txtmsg.encode(SERVER_ENCODING)
        if len(txt_bytes) == 0:
            raise SMSError('tr_txtmsg is empty.')
        elif len(txt_bytes) > 90:
            if not auto_slice:
                raise SMSError('tr_txtmsg is too long.')
            
            for txt_bytes in _slice_tr_txtmsg(tr_txtmsg=tr_txtmsg):
                self.__data.append(Data(tr_to, txt_bytes))
        else:
            self.__data.append(Data(tr_to, txt_bytes))
    
    def get(self) -> list:
        '''Get ready message | 준비된 메시지 가져옴'''
        return [Data(to, txt.decode(SERVER_ENCODING)) for to, txt in self.__data]

    def view(self):
        '''View left message count | 남은 메시지 갯수 보기

        error = {
            'message': 'xxx.xxx.xxx.xxx is not allow ip.',
            'status': '9001'
        }
        good = {
            'status': 'success',
            'curcount': '995'
        }
        '''
        post    = {
            'adminuser': self.__tr_id,
            'authkey': self.__tr_key,
            'type': 'view'
        }
        res = requests.post(SERVER_URL, data=post)

        return _parse_response(res.content)

    def cancel(self, tr_num):
        '''Cancel reservation message | 예약 메시지 취소

        :tr_num: reservation number | 예약 번호

        error = {
            'message': 'delete fail',
            'status': '9901'
        }
        good = {
            'status': 'success',
            'deletecount': '1',
            'curcount': '984'
        }
        '''
        d = datetime.datetime.now() + datetime.timedelta(days=1)

        post    = {
            'adminuser':    self.__tr_id,
            'authkey':      self.__tr_key,
            'date':         d.strftime('%Y-%m-%d %H:%M:%S'),
            'tr_num':       tr_num
        }

        res = requests.post(SERVER_URL, data=post)
        return _parse_response(res.content)

    def send(self, tr_date: datetime.datetime=None, tr_comment: str=None):
        '''Send ready message | 준비된 메세지 전송

        :tr_date: reservation datetime | 예약 일시
        :tr_comment: comment | 코멘트
        
        error = {
            'message': 'xxx.xxx.xxx.xxx is not allow ip.',
            'status': '9001'
        }
        good = {
            'status': 'success',
            'sendcount': 1,
            'phonecount': 1,
            'curcount': 993,
            'tr_num': 12345678
        }
        '''

        if not self.__data:
            raise SMSError('no data')
        
        if tr_date is None:
            tr_date_str = 0
        elif tr_date < datetime.datetime.now() +  datetime.timedelta(minutes=3):
            raise SMSError("Message reservation must be longer than 3 minutes.")
        else:
            tr_date_str = tr_date.strftime('%Y-%m-%d %H:%M:%S')
        
        if tr_comment is None:
            tr_comment = ''
        elif isinstance(tr_comment, str):
            tr_comment = tr_comment.encode(SERVER_ENCODING)

        ip = _get_my_ip()

        result_list = list()
        for tr_to, tr_msgtxt_enc in self.__data:
            post    = {
                'adminuser':    self.__tr_id,
                'authkey':      self.__tr_key,
                'rphone':       self.__tr_from,
                'phone':    tr_to,
                'sms':      tr_msgtxt_enc,
                'date':     tr_date_str,
                'msg':      tr_comment,
                'ip':       ip
            }

            res = requests.post(SERVER_URL, data=post)
            result_list.append(_parse_response(res.content))

        self.__data.clear()
        return result_list
