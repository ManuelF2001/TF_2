# Part 0 – Predict

Answers written individually, as the guide asks (Manuel Fernandes). Other
members: add yours below in the same format.

## Manuel Fernandes

**1.** Com N = 3 há 9 pares (Qr, Qw), cada um entre 1 e 3: (1,1), (1,2),
(1,3), (2,1), (2,2), (2,3), (3,1), (3,2), (3,3).

Uma leitura que começa depois de uma escrita terminada tem de a ver quando
Qr + Qw > N. Isso acontece nestes pares: (1,3), (2,2), (2,3), (3,1), (3,2),
(3,3).

Porquê: qualquer quórum de leitura cruza-se com qualquer quórum de escrita
em pelo menos um servidor. Esse servidor tem o valor mais recente. Quando
Qr + Qw ≤ 3, os quóruns podem não ter nenhum servidor em comum, e a leitura
pode devolver um valor antigo.

**2.** Cada valor é guardado com uma versão (timestamp ou número de versão,
com o ID do cliente para desempatar). O leitor devolve o valor com a versão
mais alta. Também pode reescrever esse valor nos servidores desatualizados
(read repair / write-back).

**3.** Com N = 5:

- Quóruns por maioria (Qr = Qw = 3): as leituras toleram 2 servidores em
  falha, e as escritas também 2.
- ROWA (Qr = 1, Qw = 5): as leituras toleram 4 servidores em falha, porque
  basta 1 vivo. As escritas toleram 0, porque precisam de todos os
  servidores.

## Compared with the runs

| prediction | observed | where |
|---|---|---|
| 1: Qr + Qw > N is needed | (1,2) non-intersecting under partitions, 0/3: reads returned 4, then 3, then 4, because a read asks only its own server, which write 4 had not reached | `01` §3.3, `runs/p1-nonint-partition` |
| 1: … but intersection alone is not enough | (2,2) and (1,3) intersect and still failed 0/3 under load: copies diverged and the reader had no way to tell the newest value | `01` §3.1–3.2, `runs/p1-majority-latency` |
| 1: holds for *completed* writes only | with majority quorums, a read returned a write still in progress and a later read the old value | `03` §5, kit `inversion-run`, `runs/p3-inversion` |
| 2: versions | versions alone: 0/5 under load (concurrent writes got **equal** versions) | `02` §3, `runs/p2-latency` |
| 2: + client id to break ties | `[number, client]`: 10/10 under load | `03` §2, `runs/p3-latency` |
| 2: write-back | not in Parts 1–4; added in "going further": slow link 0/3 → 3/3, cost: ROWA reads need all 5 servers | `07`, `runs/px-slow-n0`, `runs/px-rowa-crash` |
| 3: majority (3,3): 2 / 2 | reads and writes completed with n1 and n2 crashed | `03` §3 |
| 3: ROWA (1,5): 4 / 0 | reads completed, **0 writes** after one crash | `03` §3, `runs/p3-rowa-crash` |

All three answers held. Two things Part 0 did not anticipate:

- *Why* intersection is not enough: with values only, the reader receives
  the newest value but cannot recognise it (Part 1), and the intersection
  argument says nothing about writes still in progress (Part 3 Q4).
- Our write reads versions from Qr servers first, so a write needs Qr
  *and* Qw servers: (4,2) completed nothing with 2 crashes
  (`03` §3, `theory.md` §8).

Write-back, in answer 2, is the mechanism that later removes the new–old
inversion (`07-going-further.md`); the guide keeps it out of Parts 1–4.
