#!/usr/bin/env python3

# Lab 2, Part 4, questions 3-4: compare-and-set under a quorum lock.
#
# q4a.py showed lost updates: two cas read the same value and both
# succeeded. Our lock design (Part 4, question 3):
#   - before a cas, the coordinator locks the key at a lock quorum of QL
#     servers (default: a majority, N // 2 + 1). Any two majorities share a
#     server, and a server grants the lock on a key to one owner at a time,
#     so two operations can never both hold it;
#   - a server asked to lock a key that is already locked by another owner
#     refuses (lock_busy); it does not queue the request;
#   - the requester does not wait while holding part of a quorum: as soon
#     as a lock quorum is impossible (too many refusals), or LOCK_RETRY
#     seconds pass without one (crashed or unreachable servers), it
#     releases everything it got, waits a random time (so that two
#     competing requesters do not collide again and again) and tries
#     again. After LOCK_GIVE_UP seconds it answers error 11 (temporarily
#     unavailable): nothing was written, so "surely not done" is true;
#   - write takes the same lock: otherwise a write could complete between
#     the read and the write of a cas, and be silently overwritten by it;
#   - read takes no lock: it changes nothing;
#   - when the operation ends (cas_ok, error 22/20, or write_ok), the
#     coordinator sends unlock to all servers, fire and forget. A grant that
#     arrives after the attempt was abandoned or finished is unlocked at once.
# Not in this design: no lease or timeout on a lock held by a crashed or
# partitioned coordinator (the key stays locked: Part 6, question 2), no
# write-back on reads.
#
#   QR=2 QW=2 ../kit/run.sh lin-kv code/q4b.py

import logging
import random
import time
from os import environ
from types import SimpleNamespace as sn
from ms import send, reply, rpc, run, trace, set_timeout

logging.getLogger().setLevel(logging.DEBUG)

QR = int(environ.get('QR', 2))
QW = int(environ.get('QW', 2))
LOCK_RETRY = 0.25       # s without a lock quorum before releasing and retrying
LOCK_GIVE_UP = 0.8      # s after the request: answer error 11 (client timeout is 1 s)

NO_TAG = [0, '']    # tag of a missing key
store = {}          # key -> [tag, value], tag = [number, writer]
locks = {}          # key -> owner of the lock at this server
attempts = 0        # lock attempts started here, to make owners unique

def handle(msg):
    global node_id, node_ids, QL
    body = msg.body

    if body.type == 'init':
        node_id = body.node_id
        node_ids = body.node_ids
        QL = int(environ.get('QL', len(node_ids) // 2 + 1))
        logging.info('node %s initialized, QR=%d QW=%d QL=%d', node_id, QR, QW, QL)
        reply(msg, type='init_ok')

    # Client requests: this server is the coordinator.
    elif body.type == 'read':
        read(msg)
    elif body.type == 'write':
        with_lock(msg, write)
    elif body.type == 'cas':
        with_lock(msg, cas)

    # Requests from a coordinator: this server is a replica.
    elif body.type in ('get', 'put', 'lock'):
        reply(msg, **vars(serve(body, msg.src)))
    elif body.type == 'unlock':
        serve(body, msg.src)                # fire and forget: no reply

    else:
        logging.warning('unknown message type %s', body.type)

def newer(tag, other):
    # The tie-breaking rule of Part 3: compare numbers, then writer ids.
    return tuple(tag) > tuple(other)

def serve(request, src):
    # What a replica does for a coordinator (also used for our own copy).
    key = request.key
    if request.type in ('get', 'put'):
        tag, value = store.get(key, [NO_TAG, None])
    if request.type == 'get':
        return sn(type='get_ok', tag=tag, value=value)
    if request.type == 'put':
        stored = newer(request.tag, tag)
        if stored:
            store[key] = [request.tag, request.value]
        trace('put', key=key, tag=request.tag, value=request.value,
              had=[tag, value], stored=stored, coordinator=src)
        return sn(type='put_ok')
    if request.type == 'lock':
        holder = locks.get(key)
        if holder in (None, request.owner):
            locks[key] = request.owner
            trace('lock', key=key, owner=request.owner)
            return sn(type='lock_ok')
        trace('lock_busy', key=key, owner=request.owner, holder=holder)
        return sn(type='lock_busy', holder=holder)
    if request.type == 'unlock':
        if locks.get(key) == request.owner:
            del locks[key]
            trace('unlock', key=key, owner=request.owner)

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

def unlock(dest, key, owner):
    if dest == node_id:
        serve(sn(type='unlock', key=key, owner=owner), node_id)
    else:
        send(node_id, dest, type='unlock', key=key, owner=owner)

def with_lock(msg, action):
    # Take the lock on msg.body.key at QL servers, then call
    # action(msg, release); the action must call release() when it ends.
    key = msg.body.key
    start = time.monotonic()

    def attempt():
        global attempts
        attempts += 1
        owner = f'{node_id}:{attempts}'
        st = sn(phase='locking', granted=[], refused=[])

        def answer(node, a):
            if st.phase == 'done':
                if a.type == 'lock_ok':     # late grant: give it back
                    unlock(node, key, owner)
                return
            if st.phase == 'locked':        # extra grant: released at the end
                return
            (st.granted if a.type == 'lock_ok' else st.refused).append(node)
            if len(st.granted) == QL:
                st.phase = 'locked'
                timer.cancel()
                trace('locked', key=key, owner=owner, client=msg.src,
                      op=msg.body.type, granted=st.granted)
                action(msg, release)
            elif len(st.refused) > len(node_ids) - QL:
                give_up('busy')

        def release():
            st.phase = 'done'
            for dest in node_ids:
                unlock(dest, key, owner)
            trace('released', key=key, owner=owner, client=msg.src)

        def give_up(reason):
            if st.phase != 'locking':       # the timer fired too late
                return
            timer.cancel()
            release()
            delay = random.uniform(0, LOCK_RETRY)
            trace('lock_failed', key=key, owner=owner, client=msg.src,
                  reason=reason, granted=st.granted, refused=st.refused)
            if time.monotonic() - start + delay < LOCK_GIVE_UP:
                set_timeout(delay, attempt)
            else:
                trace('lock_give_up', key=key, client=msg.src, op=msg.body.type)
                reply(msg, type='error', code=11, text='key is locked')

        timer = set_timeout(LOCK_RETRY, give_up, 'timeout')
        for dest in node_ids:
            if dest != node_id:
                rpc(node_id, dest, lambda r: answer(r.src, r.body),
                    type='lock', key=key, owner=owner)
        answer(node_id, serve(sn(type='lock', key=key, owner=owner), node_id))

    attempt()

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

def put_phase(msg, key, tag, value, ok_type, release):
    # Phase 2 of write and cas: send [tag, value] to all, then, after QW
    # acknowledgements, release the lock and reply ok_type.
    def written(acks):
        trace(ok_type.replace('_ok', '_done'), key=key, tag=tag, value=value,
              client=msg.src, acks=[n for n, _ in acks])
        release()
        reply(msg, type=ok_type)

    quorum(QW, written, type='put', key=key, tag=tag, value=value)

def write(msg, release):
    key, value = msg.body.key, msg.body.value

    def tags_known(answers):
        tag = [newest(answers).tag[0] + 1, msg.src]
        trace('version', key=key, value=value, client=msg.src, tag=tag,
              seen={n: a.tag for n, a in answers})
        put_phase(msg, key, tag, value, 'write_ok', release)

    quorum(QR, tags_known, type='get', key=key)

def cas(msg, release):
    key = msg.body.key
    expected, new = getattr(msg.body, 'from'), msg.body.to   # 'from' is a keyword

    def read_done(answers):
        best = newest(answers)
        trace('cas_read', key=key, client=msg.src, read=[best.tag, best.value],
              expected=expected, to=new,
              answers={n: [a.tag, a.value] for n, a in answers})
        if best.value is None:
            release()
            reply(msg, type='error', code=20, text='key does not exist')
        elif best.value != expected:
            release()
            reply(msg, type='error', code=22,
                  text=f'expected {expected}, found {best.value}')
        else:
            put_phase(msg, key, [best.tag[0] + 1, msg.src], new, 'cas_ok', release)

    quorum(QR, read_done, type='get', key=key)

run(handle)
