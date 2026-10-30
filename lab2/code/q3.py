#!/usr/bin/env python3

# Lab 2, Part 3: concurrent writers -- versions with a tie-breaking rule.
#
# Part 2 (q2.py) let two concurrent writes get the same version; each server
# kept whichever arrived first, so servers ended up with different values
# for the same version and readers disagreed (docs/02-agree-on-newest.md).
# The rule added in Part 3, with no extra messages:
#   - a version is a tag [number, writer], where writer is the id of the
#     client that issued the write (e.g. "c6");
#   - tags are compared as pairs: first the number, then the writer id (as
#     a string). Every server and every reader applies the same rule, so
#     they all pick the same winner among two writes with equal numbers.
# We use the client id, not the coordinator's node id, because two clients
# of the same server can write concurrently: both writes would get the same
# [number, node] and the tie would remain. A client has at most one
# operation at a time, so two concurrent writes never share a writer id.
#
# Everything else is as in q2.py: a write first asks a read quorum for the
# highest tag (phase 1), then sends [number + 1, client] to all servers
# and waits for QW acknowledgements (phase 2); a read returns the value
# with the highest tag among QR answers; cas is not supported (error 10).
#
# Test hook, off by default (not part of the protocol): SLOW_PUT="n0=0.5"
# delays by 0.5 s every put that n0 sends to another server, to reproduce
# the execution of Part 3, question 4 (a write that has reached only its
# coordinator). Each delayed put is traced as "slow_put".
#
#   QR=2 QW=2 ../kit/run.sh lin-kv code/q3.py

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
    # The tie-breaking rule: compare numbers, then writer ids.
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

def write(msg):
    key, value = msg.body.key, msg.body.value

    def tags_known(answers):
        # Phase 1 done: the tag is created here.
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
