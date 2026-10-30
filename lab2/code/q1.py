#!/usr/bin/env python3

# Lab 2, Part 1: "wait for some" -- quorum reads and writes of plain values.
#
# Design of Part 1 (from the guide):
#   - each server stores, for each key, only its value;
#   - write: the receiving server (the coordinator) sends the new value to
#     all servers, itself included, and replies write_ok after QW of them
#     have acknowledged it;
#   - read: the coordinator asks all servers for their value and replies
#     after receiving QR answers;
#   - cas: error 10 (not supported).
#
# Our decision for Part 1, question 1 (what the reader returns when the QR
# answers disagree):
#   - any value beats "key does not exist": keys are never deleted, so a
#     server without the key simply has not received any write yet;
#   - among values, the reader returns the first answer it received. The
#     coordinator's own answer is always first (see quorum()), so in
#     practice: its own copy if it has the key, otherwise the first remote
#     value. Without more information there is no way to tell which value
#     is newer; this is what Part 2 fixes.
#
# Nothing else (on purpose): no versions, no ordering, no timeouts (an
# operation that never gets its quorum is never answered and the client
# times out), no retries, no read repair.
#
#   QR=2 QW=2 ../kit/run.sh lin-kv code/q1.py

import logging
from os import environ
from types import SimpleNamespace as sn
from ms import reply, rpc, run, trace

logging.getLogger().setLevel(logging.DEBUG)

QR = int(environ.get('QR', 2))
QW = int(environ.get('QW', 2))

store = {}          # key -> value

def handle(msg):
    global node_id, node_ids
    body = msg.body

    if body.type == 'init':
        node_id = body.node_id
        node_ids = body.node_ids
        logging.info('node %s initialized, QR=%d QW=%d', node_id, QR, QW)
        reply(msg, type='init_ok')

    # Client requests: this server is the coordinator.
    elif body.type == 'read':
        read(msg)
    elif body.type == 'write':
        write(msg)
    elif body.type == 'cas':
        reply(msg, type='error', code=10, text='cas not supported')

    # Requests from a coordinator: this server is a replica.
    elif body.type in ('get', 'put'):
        reply(msg, **vars(serve(body, msg.src)))

    else:
        logging.warning('unknown message type %s', body.type)

def serve(request, src):
    # What a replica does for a coordinator. Also called directly by the
    # coordinator for its own copy, so that it is "sent to itself".
    if request.type == 'get':
        return sn(type='get_ok', value=store.get(request.key))
    if request.type == 'put':
        store[request.key] = request.value
        trace('put', key=request.key, value=request.value, coordinator=src)
        return sn(type='put_ok')

def quorum(q, on_quorum, **request):
    # Send `request` to every server (this one included) and call
    # on_quorum(answers) once, when the q-th answer arrives. `answers` is a
    # list of (node, reply body) in arrival order; later answers are
    # ignored. If fewer than q servers answer, on_quorum is never called.
    # Never blocks: the remote answers are handled by rpc callbacks after
    # the current handler returns, so our own answer is always the first.
    answers = []

    def collect(node, answer):
        answers.append((node, answer))
        if len(answers) == q:
            on_quorum(answers)

    for dest in node_ids:
        if dest != node_id:
            rpc(node_id, dest, lambda r: collect(r.src, r.body), **request)
    collect(node_id, serve(sn(**request), node_id))

def read(msg):
    key = msg.body.key

    def done(answers):
        values = [a.value for _, a in answers if a.value is not None]
        trace('read', key=key, client=msg.src,
              answers={n: a.value for n, a in answers},
              returned=values[0] if values else None)
        if values:
            reply(msg, type='read_ok', value=values[0])
        else:
            reply(msg, type='error', code=20, text='key does not exist')

    quorum(QR, done, type='get', key=key)

def write(msg):
    key, value = msg.body.key, msg.body.value
    trace('write', key=key, value=value, client=msg.src)

    def done(answers):
        trace('write_done', key=key, value=value, client=msg.src,
              acks=[n for n, _ in answers])
        reply(msg, type='write_ok')

    quorum(QW, done, type='put', key=key, value=value)

run(handle)
