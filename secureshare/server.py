#!/usr/bin/env python3

import os

from flask import Flask, make_response, request, jsonify, abort
from pathlib import Path
from functools import partial

from pyaltt2.config import load_yaml, config_value
from pyaltt2.db import Database
from pyaltt2.res import ResourceStorage
from pyaltt2.converters import val_to_boolean

import pyaltt2.crypto as cr

import threading
import logging
import time

from datetime import datetime, timedelta

import pytz

import traceback

logger = logging.getLogger('gunicorn.error')

dir_me = Path(__file__).absolute().parents[1]

rs = ResourceStorage(mod='secureshare')
rq = partial(rs.get, resource_subdir='sql', ext='sql')

app = Flask(__name__)

config = load_yaml(os.getenv('SECURESHARE_CONFIG'))['secureshare']

UPLOAD_KEY = config['upload-key']

db = Database(config['db'], rq_func=rq)

EXTERNAL_URL = config.get('url', '')


def ok(data=None):
    result = {'ok': True}
    if data:
        result.update(data)
    return jsonify(result)


@app.route('/', methods=['GET'])
def index():
    return ';)'


@app.route('/ping', methods=['GET'])
def ping():
    return make_response('', 204)


@app.route('/u', methods=['POST'])
def upload():
    if request.headers.get('x-auth-key') != UPLOAD_KEY:
        abort(403)
    elif 'file' not in request.files:
        abort(400)
    f = request.files['file']
    if not f.name:
        abort(400)
    esecs = int(request.form.get('expires', config['default-expires']))
    expires = (datetime.now() + timedelta(seconds=esecs)).replace(
        tzinfo=pytz.timezone(time.tzname[0]))
    file_id = cr.gen_random_str(16)
    file_key = cr.gen_random_str(16)
    file_name = os.path.basename(f.filename)
    oneshot = val_to_boolean(request.form.get('oneshot', False))
    engine = cr.Rioja(file_key, bits=256)
    contents = engine.encrypt(f.stream.read(), b64=False)
    response = make_response('', 201)
    response.headers['Location'] = (f'{EXTERNAL_URL}/d/{file_id}/'
                                    f'{file_key}/{file_name}')
    if EXTERNAL_URL:
        response.autocorrect_location_header = False
    response.headers['Cache-Control'] = ('no-cache, no-store, must-revalidate,'
                                ' post-check=0, pre-check=0')
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = expires.isoformat() + 'Z'
    db.query('stor.add',
             id=file_id,
             fname=file_name,
             mimetype=f.mimetype,
             expires=expires,
             oneshot=oneshot,
             data=contents)
    return response


@app.route('/d/<file_id>/<file_key>/<file_name>', methods=['GET'])
def download(file_id, file_key, file_name):
    try:
        f = db.qlookup('stor.get', id=file_id, fname=file_name)
    except LookupError:
        abort(404)
    engine = cr.Rioja(file_key, bits=256)
    try:
        contents = engine.decrypt(f['data'].tobytes(), b64=False)
    except ValueError:
        abort(403)
    if f['oneshot']:
        db.query('stor.expire', id=file_id)
    response = make_response(contents)
    response.headers['Content-Type'] = f['mimetype']
    if val_to_boolean(request.args.get('raw')):
        response.headers[
            'Content-Disposition'] = f'attachment;filename={file_name}'
    return response


def clean_db():
    while True:
        logger.debug('cleaner worker running')
        try:
            db.query('delete.expired', d=datetime.now())
        except:
            logger.error(traceback.format_exc())
        time.sleep(config.get('db-clean-interval', 60))


dbconn = db.connect()

from sqlalchemy import (MetaData, Table, Column, CHAR, VARCHAR, DateTime,
                        LargeBinary, BOOLEAN)

meta = MetaData()
stor = Table('stor', meta, Column('id', CHAR(16), primary_key=True),
             Column('fname', VARCHAR(255), nullable=False),
             Column('mimetype', VARCHAR(255), nullable=False),
             Column('expires', DateTime(timezone=True), nullable=False),
             Column('oneshot', BOOLEAN, nullable=False, server_default='0'),
             Column('data', LargeBinary, nullable=False))

meta.create_all(dbconn)

dbconn.close()

threading.Thread(target=clean_db, daemon=True).start()
