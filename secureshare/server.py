#!/usr/bin/env python3

import os
import threading
import logging
import time
import traceback
import mimetypes
from hashlib import sha256
from pathlib import Path
from functools import partial, wraps

from flask import Flask, make_response, request, jsonify, abort
from sqlalchemy import (MetaData, Table, Column, CHAR, VARCHAR, DateTime,
                        LargeBinary, BOOLEAN)
from pyaltt2.config import load_yaml, config_value
from pyaltt2.db import Database
from pyaltt2.res import ResourceStorage
from pyaltt2.converters import val_to_boolean
from datetime import datetime, timedelta
import pyaltt2.crypto as cr
import pytz

logger = logging.getLogger('gunicorn.error')

dir_me = Path(__file__).absolute().parents[1]

rs = ResourceStorage(mod='secureshare')
rq = partial(rs.get, resource_subdir='sql', ext='sql')

app = Flask(__name__)

config = load_yaml(os.getenv('SECURESHARE_CONFIG'))['secureshare']

UPLOAD_KEY = config['upload-key']

db = Database(config['db'], rq_func=rq)

EXTERNAL_URL = config.get('url', '')

# list of banned user agents to block link preview fetch (startswith, lowercase)
BANNED_AGENTS = ['telegrambot', 'whatsapp', 'viber', 'facebookexternalhit']
BANNED_AGENTS_CONTAINS = ['skypeuripreview']


def ok(data=None):
    result = {'ok': True}
    if data:
        result.update(data)
    return jsonify(result)


def ok_empty():
    return make_response('', 204)


@app.route('/', methods=['GET'])
def index():
    return ';)'


@app.route('/ping', methods=['GET'])
def ping():
    return make_response('', 204)


def check_token(token):
    try:
        db.qlookup('token.get', id=token, d=datetime.now())
        return True
    except LookupError:
        return False


def auth(f):

    @wraps(f)
    def do(*args, **kwargs):
        key = request.headers.get('x-auth-key')
        if key != UPLOAD_KEY and not check_token(key):
            return make_response('Invalid upload key', 403)
        result = f(*args, **kwargs)
        if key is not None and key.startswith('token:'):
            db.query('token.delete', id=key)
        return result

    return do


@app.route('/api/v1/token', methods=['POST'])
@auth
def create_token():
    token = f'token:{cr.gen_random_str(32)}'
    d_now = datetime.now()
    esecs = int(request.form.get('expires', config['default-token-expires']))
    expires = (d_now + timedelta(seconds=esecs)).replace(
        tzinfo=pytz.timezone(time.tzname[0]))
    db.query('token.add', id=token, d=d_now, expires=expires)
    location = (f'{EXTERNAL_URL}/api/v1/token/{token}')
    response = make_response(dict(token=token, url=location), 201)
    response.headers['Cache-Control'] = ('no-cache, no-store, must-revalidate,'
                                         ' post-check=0, pre-check=0')
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = expires.isoformat() + 'Z'
    response.headers['Location'] = location
    if EXTERNAL_URL:
        response.autocorrect_location_header = False
    return response


@app.route('/api/v1/token/<token>', methods=['DELETE'])
@auth
def delete_token(token):
    if db.query('token.delete', id=token).rowcount < 1:
        abort(404)
    else:
        return ok_empty()


@app.route('/u', methods=['POST'])
@auth
def upload():
    f = request.files.get('file', request.form.get('file'))
    if f is None:
        return make_response('File not uploaded', 403)
    filename = request.form.get('fname', f.filename)
    if filename is None:
        return make_response('File name not specified', 403)
    esecs = int(request.form.get('expires', config['default-expires']))
    d_now = datetime.now()
    expires = (d_now + timedelta(seconds=esecs)).replace(
        tzinfo=pytz.timezone(time.tzname[0]))
    data = f.stream.read()
    sha256sum_gen = sha256()
    sha256sum_gen.update(data)
    sha256sum = sha256sum_gen.hexdigest()
    received_sha256sum = request.form.get('sha256sum')
    if received_sha256sum and received_sha256sum != sha256sum:
        return make_response('Checksum does not match', 422)
    file_id = cr.gen_random_str(16)
    file_key = cr.gen_random_str(16)
    filename = os.path.basename(filename)
    oneshot = val_to_boolean(request.form.get('oneshot', False))
    engine = cr.Rioja(file_key, bits=256)
    contents = engine.encrypt(data, b64=False)
    location = (f'{EXTERNAL_URL}/d/{file_id}/' f'{file_key}/{filename}')
    response = make_response(dict(url=location), 201)
    response.headers['Location'] = location
    if EXTERNAL_URL:
        response.autocorrect_location_header = False
    response.headers['Cache-Control'] = ('no-cache, no-store, must-revalidate,'
                                         ' post-check=0, pre-check=0')
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = expires.isoformat() + 'Z'
    mimetype = mimetypes.guess_type(filename)[0]
    if mimetype is None:
        mimetype = 'application/octet-stream'
    if mimetype == 'application/octet-stream':
        try:
            data.decode()
            mimetype = 'text/plain'
        except:
            pass
    db.query('stor.add',
             id=file_id,
             fname=filename,
             sha256sum=sha256sum,
             mimetype=mimetype,
             d=d_now,
             expires=expires,
             oneshot=oneshot,
             data=contents)
    return response


@app.route('/d/<file_id>/<file_key>/<file_name>', methods=['DELETE'])
@auth
def delete_upload(file_id, file_key, file_name):
    if db.query('stor.delete', id=file_id).rowcount < 1:
        abort(404)
    else:
        return ok_empty()


@app.route('/d/<file_id>/<file_key>/<file_name>', methods=['GET'])
def download(file_id, file_key, file_name):
    ua = request.headers.get('User-Agent', '').lower()
    for banned_ua in BANNED_AGENTS:
        if ua.startswith(banned_ua):
            return ''
    for banned_ua in BANNED_AGENTS_CONTAINS:
        if banned_ua in ua:
            return ''
    delete = request.args.get('c') == 'delete'
    try:
        f = db.qlookup('stor.get',
                       id=file_id,
                       fname=file_name,
                       d=datetime.now())
    except LookupError:
        abort(404)
    engine = cr.Rioja(file_key, bits=256)
    data = f['data']
    try:
        data = data.tobytes()
    except:
        pass
    try:
        contents = engine.decrypt(data, b64=False)
    except ValueError:
        abort(403)
    if delete or f['oneshot']:
        db.query('stor.delete', id=file_id)
    if delete:
        return ok()
    response = make_response(contents)
    response.headers['Content-Type'] = f['mimetype']
    response.headers['x-hash-sha256'] = f['sha256sum']
    if val_to_boolean(request.args.get('raw')):
        response.headers[
            'Content-Disposition'] = f'attachment;filename={file_name}'
    return response


def clean_db():
    while True:
        logger.debug('cleaner worker running')
        try:
            db.query('stor.delete.expired', d=datetime.now())
            db.query('token.delete.expired', d=datetime.now())
        except:
            logger.error(traceback.format_exc())
        time.sleep(config.get('db-clean-interval', 60))


dbconn = db.connect()

if 'mysql' in db.db.name:
    from sqlalchemy.dialects.mysql import DATETIME, LONGBLOB
    DateTime = partial(DATETIME, fsp=6)
    LargeBinary = LONGBLOB

meta = MetaData()
stor = Table('stor',
             meta,
             Column('id', CHAR(16), primary_key=True),
             Column('fname', VARCHAR(255), nullable=False),
             Column('sha256sum', CHAR(64), nullable=False),
             Column('mimetype', VARCHAR(255), nullable=False),
             Column('d', DateTime(timezone=True), nullable=False),
             Column('expires', DateTime(timezone=True), nullable=False),
             Column('oneshot', BOOLEAN, nullable=False, server_default='0'),
             Column('data', LargeBinary, nullable=False),
             mysql_engine='InnoDB',
             mysql_charset='utf8mb4')
tokens = Table('tokens',
               meta,
               Column('id', CHAR(38), primary_key=True),
               Column('d', DateTime(timezone=True), nullable=False),
               Column('expires', DateTime(timezone=True), nullable=False),
               mysql_engine='InnoDB',
               mysql_charset='utf8mb4')

meta.create_all(dbconn)

dbconn.close()

threading.Thread(target=clean_db, daemon=True).start()
