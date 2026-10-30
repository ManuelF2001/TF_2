#!/usr/bin/env python3

# Lab 2, Going further: a read that cannot go back in time (write-back).
#
# With q3.py, two reads that do not overlap can return first the new value
# of a write still in progress, then the old one (Part 3, questions 4-5,
# docs/03-concurrent-writers.md). The read of q3.py returns the newest
# value it SAW, but nothing guarantees that a later read will see it too:
# the write may have reached fewer than QW servers.
#
# The change (only the read; q3.py otherwise unchanged, cas still error 10):
#   - phase 1, as before: ask all servers, take the highest [tag, value]
#     among QR answers;
#   - phase 2 (new), write-back: send that [tag, value] to all servers as a
#     put and wait for QW acknowledgements BEFORE answering the client.
#     After that the value is at a write quorum, so every later read (whose
#     read quorum intersects it) sees this tag or a newer one;
#   - phase 2 is skipped when at least QW of the QR answers already carry
#     the highest tag: the value is then already at a write quorum.
#     (Possible only if QR >= QW; with ROWA, QR=1 < QW=N, every read
#     writes back to ALL servers.)
# Servers keep only the highest tag, so writing back a value they already
# have, or an older one, changes nothing.
#
# Test hook, as in q3.py: SLOW_PUT="n0=0.5" delays the puts that n0 sends
# to the other servers (write-backs included).
#
#   QR=2 QW=2 ../kit/run.sh lin-kv code/qx.py

import logging
from os import environ
from types import SimpleNamespace as sn
from ms import reply, rpc, run, trace, set_timeout

logging.getLogger().setLevel(logging.DEBUG)

QR = int(environ.get('QR', 2))
QW = int(environ.get('QW', 2))
SLOW_PUT = dict((n, float(d)) for n, _, d in
                (s.partition('=') for s in environ.get('SLOW_PUT', '').split(',') if s))

NO_TAG = [0, '']    # tag of a missing key
store = {}          # key -> [tag, value], tag = [number, writer]

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

def newer(tag, other):
    # The tie-breaking rule of Part 3: compare numbers, then writer ids.
    return tuple(tag) > tuple(other)

def serve(request, src):
    # What a replica does for a coordinator (also used for our own copy).
    tag, value = store.get(request.key, [NO_TAG, None])
    if request.type == 'get':
        return sn(type='get_ok', tag=tag, value=value)
    if request.type == 'put':
        stored = newer(request.tag, tag)
        if stored:
            store[request.key] = [request.tag, request.value]
        trace('put', key=request.key, tag=request.tag, value=request.value,
              had=[tag, value], stored=stored, coordinator=src)
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

    def send(dest):
        rpc(node_id, dest, lambda r: collect(r.src, r.body), **request)

    for dest in node_ids:
        if dest == node_id:
            continue
        if request['type'] == 'put' and node_id in SLOW_PUT:
            trace('slow_put', key=request['key'], dest=dest, tag=request['tag'],
                  delay=SLOW_PUT[node_id])
            set_timeout(SLOW_PUT[node_id], send, dest)
        else:
            send(dest)
    collect(node_id, serve(sn(**request), node_id))

def newest(answers):
    # The answer with the highest tag (tags of different writes differ).
    best = answers[0][1]
    for _, a in answers[1:]:
        if newer(a.tag, best.tag):
            best = a
    return best

def read(msg):
    key = msg.body.key

    def answer(best):
        if best.value is not None:
            reply(msg, type='read_ok', value=best.value)
        else:
            reply(msg, type='error', code=20, text='key does not exist')

    def done(answers):
        best = newest(answers)
        have = [n for n, a in answers if a.tag == best.tag]
        trace('read', key=key, client=msg.src,
              answers={n: [a.tag, a.value] for n, a in answers},
              returned=[best.tag, best.value], write_back=len(have) < QW)
        if len(have) >= QW or best.value is None:
            answer(best)            # already at a write quorum (or no value)
        else:
            quorum(QW, lambda acks: written_back(best, acks),
                   type='put', key=key, tag=best.tag, value=best.value)

    def written_back(best, acks):
        trace('write_back_done', key=key, client=msg.src, tag=best.tag,
              value=best.value, acks=[n for n, _ in acks])
        answer(best)

    quorum(QR, done, type='get', key=key)

def write(msg):
    key, value = msg.body.key, msg.body.value

    def tags_known(answers):
        tag = [newest(answers).tag[0] + 1, msg.src]
        trace('version', key=key, value=value, client=msg.src, tag=tag,
              seen={n: a.tag for n, a in answers})
        quorum(QW, lambda acks: written(tag, acks),
               type='put', key=key, tag=tag, value=value)

    def written(tag, acks):
        trace('write_done', key=key, tag=tag, value=value, client=msg.src,
              acks=[n for n, _ in acks])
        reply(msg, type='write_ok')

    quorum(QR, tags_known, type='get', key=key)

run(handle)
