# 20260506-104700 Chiplet NoI — MCTS-Only Thesis Progress

**Last updated**: 2026-05-06  
**Plan file**: `plans/20260504-151807-mcts-only-narrowed-thesis-plan.md`

---

## 1. 목표 (Thesis)

기존 RL+MCTS+greedy 앙상블을 **MCTS-only**로 단순화한다.

```
Stage 1a — MCTS-only candidate generation (7 seeds, 3 warm-start types)
Stage 1b — BookSim-based selection (best measured latency)
Stage 2  — per-workload booksim_greedy_mask (unchanged)
Baselines: Mesh, Kite-S/M/L, GIA @ iso-wire W
```

동기: 기존 "RL + MCTS + greedy" 앙상블은 reviewer에게 "kitchen-sink"로 비판받음.
MCTS-only는 단일 알고리즘 스토리로 논문이 깔끔해짐.

---

## 2. 완료된 작업

### 2-1. V3 Sweep (모두 완료)

| 파일 | 완료 |
|------|------|
| `sweep_v3_isowire_K16_N4.json` | 11/11 ✓ |
| `sweep_v3_isowire_K16_N8.json` | 7/7 ✓ |
| `sweep_v3_isowire_K32_N4.json` | 4/4 ✓ |
| `sweep_v3_isowire_K32_N8.json` | 1/1 ✓ |
| `sweep_v3_wire_scaling_K{K}_N{N}.json` | 모두 ✓ (6+5+4+2 wire pts) |

이 결과가 **RL+MCTS 앙상블 baseline**으로 사용됨.

### 2-2. Retry Cell3 RL

`retry_cell3_rl.json`:
- Round 3 best = **61.076** (kite_l target ≤ 61.1) — 겨우 통과
- RL이 한계에 도달했음을 시사

### 2-3. MCTS-Only 모듈 구현

| 파일 | 내용 |
|------|------|
| `mcts_search.py` | `MCTS_PROFILES = {'default', 'strong'}` 추가 |
| `gen_random_spine.py` | `random_hop3_spine`, `random_uniform_sample` warm-start |
| `pilot_mctsonly_k16n4.py` | K16_N4 파일럿 (11 subsets, 7 seeds, strong profile) |
| `sweep_v3_mctsonly.py` | 전체 MCTS-only iso-wire sweep driver |
| `sweep_v3_mctsonly_wirescaling.py` | wire-scaling 변형 |

**MCTS strong profile** (`MCTS_PROFILES['strong']`):

| 파라미터 | 기존 | strong |
|---------|------|--------|
| n_iters | 1500 | 5000 |
| rollout_depth | 12 | 20 |
| expansion_branch | 25 | 40 |
| rollout_branch | 8 | 12 |

**Warm-start 7 seeds 구성**:
- seeds 0-2: `greedy_union`
- seeds 3-4: `random_hop3_spine`
- seeds 5-6: `random_uniform_sample`

---

## 3. Pilot 결과 및 실패 분석

`pilot_mctsonly_k16n4.py` 실행 결과 (`results/ml_placement/pilot_mctsonly_k16n4.json`):

```
Result: 4/11 within 5% of RL+MCTS combo (need ≥9 to proceed)
*** PILOT FAILED ***
```

**패턴**:
- moe 미포함 subsets (3개): 모두 ✓
- moe 포함 subsets (8개): 모두 ✗ (worst: +204%)

**근본 원인**: 기존 surrogate (`surrogate_rate_aware.pt`)가 alloc_vec을 단 2개 스칼라로 압축.

```python
# surrogate_predict_ra 내부 — 이것이 문제
bpp = total_links / n_adj          # scalar
express_frac = n_express / total   # scalar
# 실제 어떤 pair에 링크가 있는지 전혀 모름!
```

→ 서로 다른 link 배치도 bpp/express_frac이 같으면 동일한 예측값.  
→ MCTS가 surrogate 기준으론 좋은 배치를 찾지만, BookSim 실측값은 완전히 다름.  
→ 특히 moe 같은 OOD(skewed, dense) 트래픽에서 예측 오류가 큼.

---

## 4. 현재 진행 중: Option 3b — Surrogate Retraining

### 4-1. 핵심 변경사항 (Surrogate V3)

**기존 feature (501 dim)**:
```
[traffic_496, bpp/8, express_frac, K/32, N/8, log_rate]
```

**새 feature (995 dim)**:
```
[traffic_496, alloc_flat_496 (normalized by N), K/32, N/8, log_rate]
```

`alloc_flat`을 포함시켜서 어떤 pair에 링크가 있는지 surrogate가 실제로 볼 수 있음.

### 4-2. 새로 생성된 파일

| 파일 | 내용 |
|------|------|
| `collect_surrogate_data_v2.py` | 다양한 alloc 생성 + BookSim 측정 |
| `train_surrogate_v3.py` | 새 surrogate 학습 (995 dim input) |
| `ml_express_warmstart.py` | `SurrogateV3`, `load_surrogate_v3`, `surrogate_predict_v3` 추가 |
| `mcts_search.py` | `surrogate_version='v3'` 파라미터 추가 |

### 4-3. 데이터 수집 현황 (2026-05-06 실행 중)

```bash
# 4개 프로세스 병렬 실행 중
python collect_surrogate_data_v2.py 0  # K16_N4: 500 alloc × 4 wl × 4 rate = 8000 BookSim
python collect_surrogate_data_v2.py 1  # K16_N8: 300 alloc × 4 wl × 4 rate = 4800 BookSim
python collect_surrogate_data_v2.py 2  # K32_N4: 300 alloc × 4 wl × 4 rate = 4800 BookSim
python collect_surrogate_data_v2.py 3  # K32_N8: 200 alloc × 4 wl × 4 rate = 3200 BookSim
```

| Cell | 속도 | 예상 완료 |
|------|------|-----------|
| K16_N4 | ~300/h | ~26h (내일 오전) |
| K16_N8 | ~74/h | ~65h (3일 후) |
| K32_N4 | alloc 생성 중 | - |
| K32_N8 | alloc 생성 중 | - |

로그: `collect_surr_K16_N4.log`, `collect_surr_K16_N8.log`, `collect_surr_K32_N4.log`, `collect_surr_K32_N8.log`

출력: `results/ml_placement/surrogate_data_v2_K{K}_N{N}.json`

---

## 5. 남은 작업 (순서대로)

### Step 1: K16_N4 데이터 수집 완료 대기 (~26h)

K16_N4 완료 시점에 K16_N8/K32가 아직 진행 중이어도 부분 학습 가능.  
K16_N4 데이터만으로도 파일럿 통과 여부 확인 가능.

### Step 2: Surrogate V3 학습

```bash
.venv/bin/python train_surrogate_v3.py
# 출력: results/ml_placement/surrogate_v3.pt
#       results/ml_placement/surrogate_v3.meta.json
# 소요: ~1-2h
```

학습 전 확인 사항:
- `surrogate_data_v2_K16_N4.json` 존재 및 valid 샘플 수 충분 (>1000)
- 나머지 셀 데이터도 있으면 함께 사용

### Step 3: `pilot_mctsonly_k16n4.py` V3 버전으로 재실행

`pilot_mctsonly_k16n4.py`에서 `load_rate_aware_surrogate()` →
`load_surrogate_v3()`로 교체하고, `mcts_search()` 호출에
`surrogate_version='v3'` 추가 후 재실행.

성공 기준: **≥9/11 subsets가 RL+MCTS 대비 gap ≤5%**.

### Step 4: Pilot 통과 시 — 전체 sweep 실행

```bash
# 4개 셀 병렬
.venv/bin/python sweep_v3_mctsonly.py 0 > sweep_mctsonly_K32_N8.log &
.venv/bin/python sweep_v3_mctsonly.py 1 > sweep_mctsonly_K16_N8.log &
.venv/bin/python sweep_v3_mctsonly.py 2 > sweep_mctsonly_K32_N4.log &
.venv/bin/python sweep_v3_mctsonly.py 3 > sweep_mctsonly_K16_N4.log &
```

출력: `results/ml_placement/sweep_v3_mctsonly_K{K}_N{N}.json`

### Step 5: Pilot 실패 시 — 진단 후 결정

- moe 이외 workload에서도 실패하면: surrogate 아키텍처 재검토
- K16_N8/K32도 추가 데이터 수집 후 재학습

### Step 6: Wire-scaling sweep 실행

```bash
.venv/bin/python sweep_v3_mctsonly_wirescaling.py
```

---

## 6. 파일 구조 요약

```
chiplet-noi-analysis/
├── mcts_search.py                  # MCTS 엔진 (MCTS_PROFILES 포함)
├── gen_random_spine.py             # warm-start 생성기 (hop3, uniform)
├── pilot_mctsonly_k16n4.py         # K16_N4 파일럿
├── sweep_v3_mctsonly.py            # 전체 MCTS-only sweep
├── sweep_v3_mctsonly_wirescaling.py
├── collect_surrogate_data_v2.py    # surrogate v3 학습 데이터 수집
├── train_surrogate_v3.py           # surrogate v3 학습
├── ml_express_warmstart.py         # SurrogateV3, surrogate_predict_v3 포함
└── results/ml_placement/
    ├── sweep_v3_isowire_K*.json    # RL+MCTS baseline 결과 (완료)
    ├── sweep_v3_wire_scaling_K*.json
    ├── pilot_mctsonly_k16n4.json   # MCTS-only 파일럿 결과 (failed)
    ├── surrogate_data_v2_K*.json   # v3 학습 데이터 (수집 중)
    └── surrogate_v3.pt             # (학습 후 생성 예정)
```

---

## 7. 결정 포인트

| 상황 | 액션 |
|------|------|
| Pilot ≥9/11 ✓ | `sweep_v3_mctsonly.py` 전체 실행 |
| Pilot <9/11, moe만 실패 | 데이터 더 수집 (moe subset 집중) |
| Pilot <9/11, 전반적 실패 | surrogate 아키텍처 재검토 (e.g. GNN) |
