# Exit record (four lines)

1. **Claim considered:** with N = 3, majority read/write quorums, tags
   `[number, client]` and a majority lock for writes and cas (`q4b.py`),
   completed operations are never lost or contradicted and cas is atomic,
   with one crashed or cut-off server; reads that overlap an unfinished
   write are only regular, not linearizable.
2. **Strongest evidence:** the design evolution was driven by checker
   failures that each step removed: Part 1 (values) 0/9 under load →
   Part 2 (versions) 2/10 → Part 3 (tie-break) 10/10; cas without lock 0/3
   (5 lost-update pairs in the traces) → with lock 19/19 under latency,
   crashes and partitions; and the new–old inversion reproduced on demand
   (q3 + slow link 0/3) and removed by write-back (qx 3/3).
3. **Limitation / unresolved question:** a lock whose holder crashes or
   is cut off is never released: we observed a key blocked for the rest of
   a run with only one faulty server (`runs/p4-crash-holder`,
   `runs/p4-blocked-key`); how to take
   over a lock safely without two holders (ballots/fencing, `06-compare.md`
   §2) is designed but not implemented or tested.
4. **Next action:** add fencing numbers to the lock (higher number wins,
   servers reject puts with older numbers) plus write-back on reads, and
   rerun the crash/partition scenarios with N = 5 and longer runs, checking
   for blocked keys and inversions.
