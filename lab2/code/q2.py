#!/usr/bin/env python3

# Lab 2, Part 2: "agree on the newest" -- quorums with version numbers.
#
# Part 1 failed because nobody could tell which of two values is newer
# (docs/01-wait-for-some.md). Design of Part 2 (our answer to question 1):
#   - each server stores, for each key, a pair (version, value); a missing
#     key has version 0;
#   - the version is produced by the coordinator of the write, in two
#     phases:
#       1. ask all servers for their version of the key, wait for QR
#          answers, and take version = highest + 1. Since QR + QW > N,
#          these QR answers include at least one server of the write
#          quorum of every completed write, so the new version is higher
#          than that of every completed write;
#       2. send (version, value) to all servers and reply write_ok after
#          QW acknowledgements (as in Part 1);
#   - a server stores a received pair only if its version is higher than
#     the one it has (an older or equal version is acknowledged but not
#     stored: "first one wins" on equal versions);
#   - read: ask all servers, wait for QR answers, return the value with the
#     highest version; on equal versions, the first answer received.
#   - cas: error 10 (not supported).
# Not in this design (on purpose): nothing breaks ties between two writes
# that got the same version (Part 3), no write-back on reads, no locks.
#
#   QR=2 QW=2 ../kit/run.sh lin-kv code/q2.py

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
    # What a replica does for a coordinator (also used for our own copy).
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
    # Send `request` to every server (this one included) and call
    # on_quorum(answers) once, when the q-th answer arrives; answers is a
    # list of (node, reply body) in arrival order (ours first).
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
    # The answer with the highest version; max() keeps the first of equals,
    # i.e. the first answer received.
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

    def versions_known(answers):
        # Phase 1 done: the version is created here.
        version = newest(answers).version + 1
        trace('version', key=key, value=value, client=msg.src,
              version=version, seen={n: a.version for n, a in answers})
        quorum(QW, lambda acks: written(version, acks),
               type='put', key=key, version=version, value=value)

    def written(version, acks):
        trace('write_done', key=key, version=version, value=value,
              client=msg.src, acks=[n for n, _ in acks])
        reply(msg, type='write_ok')

    quorum(QR, versions_known, type='get', key=key)

run(handle)
