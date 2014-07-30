# -*- coding: utf-8 -*-

import os

os.environ['MOMOKO_TEST_DB'] = 'vircgame'
os.environ['MOMOKO_TEST_PASSWORD'] = '11'
os.environ['MOMOKO_TEST_HOST'] = 'localhost'
os.environ['MOMOKO_TEST_USER'] = 'vircgamecom'

# SERVER_ADDRESS = '178.17.164.68:8888'  # dev
SERVER_ADDRESS = '178.175.136.50:8888'  # master


def set_database_settings():
    db_database = os.environ.get('MOMOKO_TEST_DB', 'momoko_test')
    db_user = os.environ.get('MOMOKO_TEST_USER', 'postgres')
    db_password = os.environ.get('MOMOKO_TEST_PASSWORD', '')
    db_host = os.environ.get('MOMOKO_TEST_HOST', '')
    db_port = os.environ.get('MOMOKO_TEST_PORT', 5432)
    enable_hstore = True if os.environ.get('MOMOKO_TEST_HSTORE', False) == '1' else False
    dsn = 'dbname=%s user=%s password=%s host=%s port=%s' % (
        db_database, db_user, db_password, db_host, db_port)

    assert (db_database or db_user or db_password or db_host or db_port) is not None, (
        'Environment variables for the examples are not set. Please set the following '
        'variables: MOMOKO_TEST_DB, MOMOKO_TEST_USER, MOMOKO_TEST_PASSWORD, '
        'MOMOKO_TEST_HOST, MOMOKO_TEST_PORT')

    return dsn