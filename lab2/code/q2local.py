#!/usr/bin/env python3

# Lab 2, Part 2, alternative answer to question 1 (for the checkpoint, where
# groups that chose differently compare their runs).
#
# Identical to q2.py except for WHO produces the version and HOW: the
# coordinator takes the version from its OWN copy, without asking anyone
# (version = own version of the key + 1), and goes straight to the put
# phase. One round trip per write instead of two, like a Lamport clock per
# key. The flaw we expect: a coordinator that was not in the write quorum
# of the latest write has an old version, so its new write gets a version
# that is equal to or lower than a write that already completed, and the
# servers ignore it (docs/02-agree-on-newest.md).
#
#   QR=2 QW=2 ../kit/run.sh lin-kv code/q2local.py

import logging
from os import environ
from types import SimpleNamespace as sn
from ms import reply, rpc, run, trace

logging.getLogger().setLevel(logging.DEBUG)

QR = int(environ.get('QR', 2))
QW = int(environ.get('QW', 2))

store = {}          # key -> [version, value]; missing key = version 0

def handle(msg):
    global node_id, node_ids
    body = msg.body

    if body.type == 'init':
        node_id = body.node_id
        node_ids = body.node_ids
        logging.info('node %s initialized, QR=%d QW=%d', node_id, QR, QW)
        reply(msg, type='init_ok')

    elif body.type == 'read':
        read(msg)
    elif body.type == 'write':
        write(msg)
    elif body.type == 'cas':
        reply(msg, type='error', code=10, text='cas not supported')

    elif body.type in ('get', 'put'):
        reply(msg, **vars(serve(body, msg.src)))

    else:
        logging.warning('unknown message type %s', body.type)

def serve(request, src):
    version, value = store.get(request.key, [0, None])
    if request.type == 'get':
        return sn(type='get_ok', version=version, value=value)
    if request.type == 'put':
        stored = request.version > version
        if stored:
            store[request.key] = [request.version, request.value]
        trace('put', key=request.key, version=request.version,
              value=request.value, had=[version, value], stored=stored,
              coordinator=src)
        return sn(type='put_ok')

def quorum(q, on_quorum, **request):
    answers = []

    def collect(node, answer):
        answers.append((node, answer))
        if len(answers) == q:
            on_quorum(answers)

    for dest in node_ids:
        if dest != node_id:
            rpc(node_id, dest, lambda r: collect(r.src, r.body), **request)
    collect(node_id, serve(sn(**request), node_id))

def newest(answers):
    return max((a for _, a in answers), key=lambda a: a.version)

def read(msg):
    key = msg.body.key

    def done(answers):
        best = newest(answers)
        trace('read', key=key, client=msg.src,
              answers={n: [a.version, a.value] for n, a in answers},
              returned=[best.version, best.value])
        if best.value is not None:
            reply(msg, type='read_ok', value=best.value)
        else:
            reply(msg, type='error', code=20, text='key does not exist')

    quorum(QR, done, type='get', key=key)

def write(msg):
    key, value = msg.body.key, msg.body.value

    # The only difference with q2.py: the version comes from our own copy.
    version = store.get(key, [0, None])[0] + 1
    trace('version', key=key, value=value, client=msg.src, version=version,
          seen={node_id: version - 1})

    def written(acks):
        trace('write_done', key=key, version=version, value=value,
              client=msg.src, acks=[n for n, _ in acks])
        reply(msg, type='write_ok')

    quorum(QW, written, type='put', key=key, version=version, value=value)

run(handle)
