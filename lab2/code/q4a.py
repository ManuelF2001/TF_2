#!/usr/bin/env python3

# Lab 2, Part 4, question 1: compare-and-set on the quorum store, no lock.
#
# Same store as q3.py (tags [number, client], highest tag wins, QR/QW
# quorums), plus cas exactly as the guide describes it:
#   1. read from a quorum: ask all servers, wait for QR answers, take the
#      value with the highest tag (traced as "cas_read");
#   2. compare: key missing -> error 20; value != from -> error 22;
#   3. otherwise write `to` as a write would: tag [highest number + 1,
#      client], sent to all servers, cas_ok after QW acknowledgements.
# Nothing makes the read-compare-write atomic: two cas that read the same
# value can both succeed (lost update, docs/04-compare-and-set.md).
# (The SLOW_PUT test hook of q3.py is not needed here and was left out.)
#
#   QR=2 QW=2 ../kit/run.sh lin-kv code/q4a.py

import logging
from os import environ
from types import SimpleNamespace as sn
from ms import reply, rpc, run, trace

logging.getLogger().setLevel(logging.DEBUG)

QR = int(environ.get('QR', 2))
QW = int(environ.get('QW', 2))

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
        cas(msg)

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

    for dest in node_ids:
        if dest != node_id:
            rpc(node_id, dest, lambda r: collect(r.src, r.body), **request)
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

    def done(answers):
        best = newest(answers)
        trace('read', key=key, client=msg.src,
              answers={n: [a.tag, a.value] for n, a in answers},
              returned=[best.tag, best.value])
        if best.value is not None:
            reply(msg, type='read_ok', value=best.value)
        else:
            reply(msg, type='error', code=20, text='key does not exist')

    quorum(QR, done, type='get', key=key)

def put_phase(msg, key, tag, value, ok_type):
    # Phase 2 of write and cas: send [tag, value] to all, reply ok_type
    # (write_ok / cas_ok) after QW acknowledgements.
    def written(acks):
        trace(ok_type.replace('_ok', '_done'), key=key, tag=tag, value=value,
              client=msg.src, acks=[n for n, _ in acks])
        reply(msg, type=ok_type)

    quorum(QW, written, type='put', key=key, tag=tag, value=value)

def write(msg):
    key, value = msg.body.key, msg.body.value

    def tags_known(answers):
        tag = [newest(answers).tag[0] + 1, msg.src]
        trace('version', key=key, value=value, client=msg.src, tag=tag,
              seen={n: a.tag for n, a in answers})
        put_phase(msg, key, tag, value, 'write_ok')

    quorum(QR, tags_known, type='get', key=key)

def cas(msg):
    key = msg.body.key
    expected, new = getattr(msg.body, 'from'), msg.body.to   # 'from' is a keyword

    def read_done(answers):
        best = newest(answers)
        trace('cas_read', key=key, client=msg.src, read=[best.tag, best.value],
              expected=expected, to=new,
              answers={n: [a.tag, a.value] for n, a in answers})
        if best.value is None:
            reply(msg, type='error', code=20, text='key does not exist')
        elif best.value != expected:
            reply(msg, type='error', code=22,
                  text=f'expected {expected}, found {best.value}')
        else:
            put_phase(msg, key, [best.tag[0] + 1, msg.src], new, 'cas_ok')

    quorum(QR, read_done, type='get', key=key)

run(handle)
