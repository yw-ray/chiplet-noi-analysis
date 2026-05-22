# LegoSim popnet cross-validation plan

Date: 2026-05-22
Status: Plan only — implementation not started

## Goal

우리 BookSim 측정 결과 (특히 K=16 N=8 ep_all_to_all probe +86%, K=32
catastrophic regime)가 *BookSim 자체의 artifact가 아님*을 cross-simulator
로 확증. LegoSim에 통합된 **popnet** (cycle-accurate NoC simulator,
Tsinghua/FCAS-LAB) 으로 동일 cell을 재측정해서 BookSim과 비교.

Paper 측면: §5.x "Cross-Simulator Validation" 추가 → reviewer의 standard
critique ("did you check on a different simulator?") 차단.

## Current state (as of 2026-05-22)

이미 완료:
- LegoSim repo cloned: `legosim/` (root)
- Submodules updated (gem5, gpgpu-sim, snipersim, popnet_chiplet 등)
- `cmake`, `libboost-all-dev` 설치됨
- **popnet built**: `legosim/popnet_chiplet/build/popnet` (10MB, working)
- Sample run verified: 9x9 mesh + random trace → avg lat 35.5 + power

아직 안 한 것:
- BookSim alloc → popnet `.gv` topology converter
- BookSim traffic matrix → popnet trace file converter
- Cross-validation harness
- 첫 cell 측정

## Architectural diff (BookSim vs popnet)

| 축 | BookSim | popnet |
|---|---|---|
| Topology spec | anynet (router-router pairs) | GraphViz `.gv` |
| Traffic spec | matrix file (우리 patch) | trace file `T sx sy dx dy n` |
| Router 단위 | 1 router per internal mesh node | 1 router per topology node |
| Routing | `routing_function = min` | `-R 0` (XY/dimension) |
| Seed | `seed = N` (우리 patch) | `-r N` |
| Cycle 단위 | sim cycle | sim cycle (단위 비교 미확인) |
| Output | "Packet latency average" | "average Delay" |
| Bonus | — | total power (mem + crossbar + arbiter + link) |

핵심 모름:
- popnet의 cycle unit이 BookSim과 1:1 동일한지 (absolute lat 비교 가능?)
- popnet `-V 3 -B 12 -O 12 -F 4` (VC=3, buf=12, out=12, flit=4)이 BookSim
  `num_vcs=8 vc_buf_size=16 packet_size=8` 와 어떻게 mapping?
- → **첫 sanity로 같은 mesh + 같은 uniform traffic을 양쪽에 던져서 lat
  scale calibration**

## Cross-validation 디자인 (3-step pipeline)

### Step 1: `bs_to_popnet_gv.py` — topology converter

Input: BookSim alloc dict `{(ci, cj): n_links}` + grid shape (R, C) +
chip_rows × chip_cols

Output: popnet `.gv` GraphViz file

알고리즘:
1. 각 chiplet `c` 내부 mesh router 노드 `c*N+r` (r ∈ [0, N))
2. Internal mesh edges (router-router within chiplet)
3. Inter-chiplet edges per alloc: BookSim `gen_booksim_config`의
   border-router pairing 로직 그대로 (`noi_topology_synthesis.py:269-292`
   참조) — `min(n_links, len(border))` 캡 포함
4. `.gv` 파일에 `graph G { ... 0--1 ... }` 형식으로 dump

참고할 기존 코드:
- `noi_topology_synthesis.py:250-300` (gen_booksim_config)
- `legosim/popnet_chiplet/test/mesh_4_4.gv` (mesh example)
- `legosim/artifact/matmul/topology/NVL_6_6_flit_4.gv` (express example)

### Step 2: `matrix_to_popnet_trace.py` — traffic converter

Input: K×K chiplet-level traffic matrix T, injection rate, simulation
length, NPC (nodes per chiplet)

Output: popnet trace file (text)

알고리즘:
1. Chiplet-level T를 node-level (K*N × K*N)로 expand
   (`gen_traffic_matrix_file`의 expansion 로직 참조,
   `noi_topology_synthesis.py:335-363`)
2. 각 (src_node, dst_node) pair의 rate × T_total = expected packets
3. Poisson process로 packet event 생성:
   - inter-arrival time ~ Exp(rate)
   - 누적 시간 < T_total 까지 반복
4. 각 event 한 줄: `<time:%.4e> <sx> <sy> <dx> <dy> <packet_size>`
   - popnet은 2D coord (sx, sy)이므로 node index를 (sx, sy)로 매핑:
     `sx = node // (sqrt_total), sy = node % sqrt_total`
   - 또는 `-c 1` (1D) 모드로 node index 그대로 사용 가능 (좀 더 단순)

### Step 3: `cross_validate.py` — driver + comparator

각 (cell, workload, alloc, seed)에 대해:
1. BookSim 측정 (이미 multiseed_variance, probe_predictor에 있음)
2. 같은 setup으로 popnet:
   - `.gv` 생성 (Step 1)
   - trace 생성 (Step 2)
   - `popnet -A <sqrt(K*N)> -c 2 -V 3 -B 12 -O 12 -F 4 -L 1000 -T 20000
     -r <seed> -I <trace> -R 0 -G <gv>`
3. 두 lat 추출, ratio 계산
4. probe_gain 둘 다 계산해서 차이 추적

JSON 출력: `results/ml_placement/cross_validation_popnet.json`

## Implementation 순서 + cost

### Phase 1: Sanity calibration (priority highest, ~2시간)

목표: BookSim과 popnet의 *cycle unit*이 일치하는지, 작은 cell에서 lat이
같은 scale인지 확인.

작업:
- K=4 N=4 (작은 cell) mesh alloc만 사용
- uniform_random traffic 한 가지
- 5 seeds 각각 BookSim + popnet 실행
- lat 비교 → ratio 일관적이면 unit consistent

비용: harness 코드 작성 ~1시간 + 실측 ~10분 + 비교 분석 ~30분

성공 기준:
- popnet lat / BookSim lat ratio가 5 seeds에서 ±20% 이내로 일관
- 만약 ratio 큼차이 → cycle unit calibration factor 필요

### Phase 2: First strong-case validation (priority high, ~2시간)

대상: **K=16 N=8 ep_all_to_all (probe +86%)** — 우리 paper의 가장
striking finding.

작업:
- 동일 (mesh, mesh+1) alloc을 popnet에서 측정
- 5 seeds
- BookSim probe_gain = +86% vs popnet probe_gain = ?

비용: trace file 크기 좀 큼 (K*N = 128 router × T_total cycles) ~5분/run.
2 allocs × 5 seeds = 10 runs ~50분 + 분석 ~30분

성공 기준 + 결과 해석:
- popnet도 probe_gain > +50% → **강한 confirmation, paper에 그대로**
- popnet probe_gain 작음 → 차이의 원인 분석 (routing? VC?)
- popnet도 catastrophic 보이지만 다른 magnitude → 두 결과 honestly 보고

### Phase 3: Catastrophic regime validation (priority medium, ~3시간)

대상: K=32 N=8 hybrid_tp_pp / uniform_random (probe −528%, −748%)

작업:
- 동일 alloc 측정
- 5 seeds (catastrophic regime이라 variance 클 가능성)
- BookSim의 catastrophic이 popnet에서도 나타나는지

비용: K=32 N=8 = 256 router 매우 큼. ~10분/run × 2 × 5 = 100분 + 분석

성공 기준:
- popnet도 catastrophic (probe < −50%) → 강한 confirmation
- popnet probe ≈ 0 → BookSim 특유 routing artifact 가능성, 추가 조사

### Phase 4: Full sweep (priority low, overnight)

12 cells × 7 workloads × 2 allocs × 5 seeds = 840 popnet runs

비용: 평균 5분/run × 8-way parallel = ~9시간. Overnight.

성공 기준 + paper 활용:
- BookSim과 popnet의 (probe_gain) 84 data point Spearman ρ
- 만약 ρ > 0.7 → 둘이 같은 phenomenon 측정 → paper에 단호한 cross-validation 결과
- 만약 ρ < 0.5 → 두 simulator가 다른 phenomenon 측정 → 둘 다 보고 + methodology section 보강

## Risk + mitigation

1. **Cycle unit mismatch**: popnet과 BookSim의 cycle 단위가 다를 수 있음.
   Phase 1 sanity로 즉시 발견. mitigation: scale factor 명시 + relative
   비교 (ratio, probe_gain%) 위주.

2. **Topology 의미 차이**: popnet의 inter-chiplet edge가 BookSim의 router-
   router link과 정확히 같은 의미인지 모름. Phase 1에서 같은 mesh로
   verify. mitigation: 안 맞으면 graphviz weight 조정으로 calibration.

3. **Trace file size**: K=32 N=16 = 512 nodes × sim length 100K cycles
   × packet rate → trace file 수십 MB 가능. mitigation: streaming
   generation, gzip.

4. **Routing algorithm 차이**: popnet `-R 0` (dimension routing)이
   BookSim `routing_function=min`과 *fully* 같지 않을 수 있음. min은
   shortest path, dimension은 XY. express link 있을 때 routing decision
   다를 가능성. mitigation: 둘의 routing function 비교 후 평행 적용.

5. **popnet의 `-G` 토폴로지 의미**: README는 "임의 토폴로지" 지원
   언급하지만 구체 동작 미확인. mitigation: NVL_6_6 같은 prior example
   참조 후 우리 case 적용.

6. **첫 가장 cost: harness 코드 작성**. 만약 Phase 1 sanity에서 calibration
   fail하면 — popnet usage에 일주일+ 들였는데 cross-validation 못 함.
   mitigation: Phase 1 quick failure 시 paper에 "popnet attempted, abandoned
   due to incompatible cycle unit" 정도로 명시 가능.

## Decision points

### 다음 session 시작 시 가장 먼저
1. `legosim/popnet_chiplet/build/popnet` 살아있나 (build 결과 보존됨)
2. Phase 1 harness 코드부터 시작

### Phase 1 결과 (sanity calibration) 후
- 일치 → Phase 2 진입
- 불일치 → calibration 추가 또는 paper validation 포기

### Phase 2 결과 (K=16 N=8 ep) 후
- confirmation 강함 → Phase 3 / 4 진행
- 약함 → Phase 3에서 catastrophic regime만 보고 마무리

## File list (will create)

- `bs_to_popnet_gv.py` — BookSim alloc → popnet `.gv`
- `matrix_to_popnet_trace.py` — traffic matrix → popnet trace
- `cross_validate.py` — driver + comparator
- `results/ml_placement/cross_validation_popnet.json` — 결과 저장
- (optional) `plot_cross_validation.py` — figure generation

## References (existing code to reuse)

- `noi_topology_synthesis.py:250-330` — `gen_booksim_config`, `gen_traffic_matrix_file`
- `multiseed_variance_k32n4.py` — BookSim multi-seed harness (이걸 base로 popnet 버전 만들기)
- `probe_predictor.py` — 12-cell sweep harness
- `legosim/popnet_chiplet/test/mesh_4_4.gv` — mesh topology example
- `legosim/artifact/matmul/topology/NVL_6_6_flit_4.gv` — express topology example
- `legosim/popnet_chiplet/random_trace/bench` — trace file example
- `legosim/popnet_chiplet/configuration.cc:35-130` — popnet CLI option handling

## Sanity-check command (Phase 1 quick verify)

```
# After harness coded:
cd /home/youngwoo/grepo/research/chiplet-noi-analysis
python3 cross_validate.py --cell K4_N4 --workload uniform_random \
    --alloc mesh --seeds 1,2,3,4,5

# Expected: BookSim lat ≈ 21.7 (we have this from probe_predictor data)
# popnet lat: TBD — should be same ballpark if cycle unit matches
```

## Paper integration (deferred, after Phase 2+ success)

새 section 후보 §5.x:
```latex
\subsection{Cross-Simulator Validation}
\label{sec:popnet}

To rule out BookSim-specific measurement artifacts, we re-ran key cells
on popnet, the cycle-accurate NoC simulator from the LegoSim
heterogeneous-chiplet framework [cite]. Across N cells with M-seed
medians, popnet's measured probe gain on K=16,N=8,
ep_all_to_all matched our BookSim measurement to within ±X%
(Table~\ref{tab:cross_val}). The catastrophic regime on K=32,N=8 is
also reproduced (popnet probe_gain Y vs BookSim Z), confirming the
phenomenon is a structural property of single express-link placement
under saturation rather than a simulator-specific artifact.
```

Table 후보 (한 row per validated cell):
| Cell | Workload | BookSim probe% | popnet probe% | abs diff |

## When to abandon

만약 Phase 2까지 가서도 popnet/BookSim 일치도 매우 낮으면:
- paper에 cross-validation 시도 자체를 *limitation*으로 명시
- "popnet integration explored but cycle unit + routing calibration
  remained open; we leave this to future work"
- 시간 추가 투자 안 함
