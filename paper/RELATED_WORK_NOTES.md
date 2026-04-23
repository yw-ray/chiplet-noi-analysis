# Related Work Notes — Chiplet NoI Topology & Express Links

`paper/main.tex` 의 bibliography 에 실린 NoI 관련 선행 연구를 정리한 실무 노트입니다.
각 항목마다 **(a) 핵심 주장, (b) 확인된 수치/벤치마크, (c) 우리 연구와의 차이** 를 기록합니다.

## 표기 규약

- **[CONFIRMED]**: 원문을 직접 확인했거나 `paper/main.tex` 에 명시 인용된 내용
- **[FROM CITATION]**: main.tex 의 `\bibitem` 레벨 메타데이터 (제목/저자/venue)
- **[GENERAL KNOWLEDGE]**: 분야 상식 수준, 원문 재확인 권장
- **[UNCERTAIN — NEEDS RE-READ]**: 구체 수치는 원문 재검증 필요

---

## Tier 1: 직접 경쟁 또는 가장 가까운 선행

### PARL — Shukla et al., arXiv:2510.24113 (Oct 2025)

**"Taming the Tail: NoI Topology Synthesis for Mixed DL Workloads on Chiplet-Based Accelerators"**

- [CONFIRMED] 저자: A. Shukla, H. Sharma, S. Bharadwaj, V. Abrol, S. Deb.
- [CONFIRMED] 접근: **cold-start maskable PPO** (PPO + action masking) — 주어진 budget 에서 NoI topology 를 생성.
- [CONFIRMED] 타깃 문제: **multi-objective Interference Score** 최소화 (여러 tenant 사이의 간섭/tail latency).
- [CONFIRMED] 설정: **heterogeneous** chiplet (MI300X-class: compute + memory 혼합), **multi-tenant** DL workload.
- [CONFIRMED] 한계 (우리 관점):
  - workload-level predictor 없음
  - strong heuristic 으로부터 warm-start 없음
  - deterministic baseline 대비 worst-case 보장 없음
- **우리와의 차이 (Table 1 요약)**:
  | Axis | PARL | Ours |
  |---|---|---|
  | Predictor | No | **NL%** |
  | Warm-start | No (cold PPO) | **Greedy allocator** |
  | Safety | None | **$\le$ Greedy (post-hoc fallback)** |
- **왜 head-to-head reproduction 안 했나** [CONFIRMED from main.tex:71]: multi-objective reward + interference evaluator 를 BookSim trace 위에 재구현해야 해서 비용 큼. Qualitative positioning 으로 대체. 대신 cold-start 변종 RL 을 §VI.F ablation 에 넣어 proxy 로 삼음 (cold RL worst = +11.3% vs greedy, warm = +1.7% 전, +0.0% 후).

---

### Kite — Bharadwaj et al., DAC 2020

**"Kite: A Family of Heterogeneous Interposer Topologies Enabled via Accurate Interconnect Modeling"**

- [FROM CITATION] DAC 2020 published.
- [GENERAL KNOWLEDGE] adjacent-only interposer topology 의 **variant family** 를 정의하고 RC-based interconnect 모델로 energy/delay/area 를 비교.
- [CONFIRMED from main.tex:65] 한계 (우리 관점): adjacent pair 사이의 link 배치/할당 최적화 에 국한. **Non-adjacent express link 는 다루지 않음.** Phantom load 의 구조적 원인 (non-adj 트래픽의 multi-hop 전이) 자체를 제거 못 함.
- 인용 위치: §I intro, §II related work "Adjacent-only NoI design".

---

### Florets — Sharma et al., ACM TECS 2023

**"Florets for Chiplets: Data Flow-aware NoI for CNN Inference"** (vol. 22, no. 6)

- [FROM CITATION] ACM TECS 2023.
- [GENERAL KNOWLEDGE] CNN inference 특화: data-flow graph 로부터 chiplet 간 traffic demand 를 추론해 adjacent link 배치 최적화.
- [UNCERTAIN — NEEDS RE-READ] 평가 workload 는 ResNet/MobileNet 계열 CNN 이며 LLM training workload 는 비포함 (재확인 필요).
- 한계 (우리 관점): Kite 와 동일 — adjacent-only. LLM TP/PP/MoE 류 traffic 패턴 미검증.

---

### Modular Routing — Yin et al., ISCA 2018

- [FROM CITATION] ISCA 2018.
- [GENERAL KNOWLEDGE] chiplet 별로 routing algorithm 을 modular 로 구성해 deadlock-free 조합을 자동 생성.
- 우리와의 연결: routing 계층 독립성 — express link 의 이득이 routing 알고리즘과 무관함을 주장할 때 배경 문헌.

---

## Tier 2: NoC 고전 (express bypass & concentrated)

### Express Virtual Channels (EVC) — Kumar et al., ISCA 2007

- [FROM CITATION] ISCA 2007.
- [GENERAL KNOWLEDGE] single-die NoC 에서 **dedicated VC 로 intermediate hop bypass**.
- [UNCERTAIN — NEEDS RE-READ] 원 논문이 보고한 latency/throughput 수치는 8x8 mesh 등 NoC context. 실제 수치 인용 시 원문 재확인 필수.
- [CONFIRMED from main.tex:68] 우리와의 차이: chiplet 외부 interposer wire 는 die-edge PHY + 물리 wire 라서 monolithic NoC 의 VC bypass 와 근본 다름. Express link 는 **물리적 direct wire**, VC 라는 버퍼 개념과 별개.

### Concentrated Mesh (C-Mesh) — Balfour & Dally, ICS 2006

- [FROM CITATION] ICS 2006.
- [GENERAL KNOWLEDGE] tiled CMP 에서 여러 core 가 한 router 공유 (전형적으로 4:1 concentration). Router radix 유지하면서 hop count 감소.
- [CONFIRMED from main.tex:68] 우리와의 차이: tile 내부 공유 구조라 chiplet **경계를 넘는 문제** (die-edge PHY 자원 경합, UCIe 점대점 제약) 와 무관.

---

## Tier 3: Chiplet 시스템 비용/평가 인프라

### Chiplet Actuary — Feng et al., DAC 2022

**"Chiplet Actuary: A Quantitative Cost Model"**

- [FROM CITATION] DAC 2022.
- [GENERAL KNOWLEDGE] die yield, bonding cost, package cost, NRE 를 모델링해 monolithic vs chiplet 경제성 정량 분석.
- [UNCERTAIN — NEEDS RE-READ] 논문이 제시한 breakeven chiplet 수 / yield curve 세부 수치는 원문 재확인.
- 우리와의 연결: express link 추가 는 interposer wire 자원 소모 → overhead 논의 (§VI 물리 overhead) 시 배경.

### CATCH — arXiv:2503.15753, 2025

**"Cost Analysis Tool for Chiplet-based Systems"**

- [FROM CITATION] arXiv 2503.15753 (2025).
- [UNCERTAIN — NEEDS RE-READ] Chiplet Actuary 의 후속격 tool; 세부 내용 미확인.

### CPElide — Dalmia et al., MICRO 2024

**"CPElide: Efficient Multi-Chiplet GPU Synchronization"**

- [FROM CITATION] MICRO 2024.
- [GENERAL KNOWLEDGE] multi-chiplet GPU 의 불필요 synchronization 제거(elide) 로 barrier 오버헤드 감소.
- 우리와의 간접 연결: chiplet 간 traffic pattern 이 sync barrier 로 결정된다는 관점 — tree_allreduce workload 모델의 현실성 지지.

### CnSim — Feng & Wei, USENIX ATC 2024

**"Evaluating Chiplet-based Networks via Cycle-Accurate Simulation"**

- [FROM CITATION] USENIX ATC 2024.
- [GENERAL KNOWLEDGE] BookSim 위에 chiplet-specific D2D 계층을 얹은 시뮬레이터.
- 우리 선택: 재현성과 기존 baseline 과의 호환성을 위해 BookSim 2.0 + anynet topology 사용. CnSim 은 향후 cross-validation 대상.

### BookSim 2.0 — Jiang et al., ISPASS 2013

- [CONFIRMED] 우리가 실제 사용 중인 cycle-accurate NoC simulator.
- [GENERAL KNOWLEDGE] anynet topology 로 임의 그래프 구조 지원 — 우리 express link 실험 가능 이유.

---

## Tier 4: 표준 / 하드웨어 레퍼런스

### UCIe — Sharma et al., IEEE Micro 2024

**"UCIe: Standard for an Open Chiplet Ecosystem"**

- [FROM CITATION] IEEE Micro 2024.
- [CONFIRMED from main.tex:103] 핵심 제약: UCIe 1.x / 2.0 D2D PHY 는 **strictly point-to-point**. 즉 on-interposer switching fabric 을 표준상 허용하지 않음 → 우리가 switch topology (예: FBfly with shared router) 대신 **direct wire express** 를 쓰는 근거.
- [UNCERTAIN — NEEDS RE-READ] UCIe Advanced per-lane bandwidth (대략 16~32 GT/s 범주, 재확인 필요), die-edge beachfront density (수백 GB/s/mm 범주).

### NVIDIA Blackwell — Technical Brief 2024

- [FROM CITATION] NVIDIA official brief, 2024.
- [GENERAL KNOWLEDGE] B200: 2-die package, NVLink/NVLink-C2C 기반 interposer.
- 우리 intro 의 "chiplet count 증가 중" motivation.

### AMD MI300X — Smith et al., Hot Chips 2024

- [FROM CITATION] Hot Chips 2024.
- [GENERAL KNOWLEDGE] 8 compute chiplet + memory chiplet stack (heterogeneous), CoWoS 기반 2.5D.
- 우리 motivation 의 현실 precedent.

---

## 우리 논문과의 비교 요약 (Table 1 확장판)

| Axis | Kite | Florets | PARL | EVC/C-mesh | Chiplet Actuary | Ours |
|---|---|---|---|---|---|---|
| Non-adj express link | No | No | **Yes** | Intra-die only | N/A (cost model) | **Yes, explicit placement** |
| Warm-start from heuristic | N/A | N/A | **No (cold PPO)** | N/A | N/A | **Yes (greedy allocator)** |
| Simulation-free predictor | No | No | No | No | N/A | **Yes (NL%)** |
| Worst-case guarantee | N/A | N/A | **None** | N/A | N/A | **Yes (post-hoc fallback $\le$ greedy)** |
| Target workload | Generic DL | CNN inference | Mixed DL (multi-tenant) | Generic NoC | Cost modeling | **LLM training (Tree/Hybrid/MoE/Uniform)** |
| Primary metric | Energy/delay | Data-flow aware | p99 tail latency | Hop count | Dollar cost | **Mean latency + NL% correlation (ρ=0.744, τ=0.593 over 40 cells)** |

---

## Paper 의 직접 인용된 본문 수치 (for cross-check)

- $\alpha_{\max} = \sqrt{K} \cdot \lfloor K/4 \rfloor = \Theta(K^{3/2})$ — Theorem/Corollary (§II).
- Interposer 신호 층: **3--6 signal layers** in CoWoS-class. [CONFIRMED, main.tex:103]
- Reticle-bounded interposer area: **$\le 2500\,$mm$^2$**. [CONFIRMED, main.tex:103]
- Express link wire-delay model: **$2d$ cycles for distance-$d$ link**. [CONFIRMED, main.tex:475]
- $\lambda$-sensitivity (wire delay scaling) 결과 (12 cell) — Tree AR: +17.7%→+14.3%, Hybrid: +47.5%→+41.9%, Uniform: +46.9%→+42.3%, MoE: +56.5%→+52.5% (λ=1.0→2.0). [CONFIRMED, main.tex:475]
- Cold RL worst-case vs greedy: **+11.3%**; warm-start: **+1.7%** before fallback, **+0.0%** after. [CONFIRMED, main.tex:71]

---

## 아직 읽지 않았지만 서베이에 추가 검토할 후보

- **SLoT / chiplet placement** — 최신 arXiv (2024~2025) NoI 배치 최적화 후보
- **NoI for DLRM (recommendation models)** — MICRO/ISCA 2024 후보
- **Chimera, SPEED** 등 chiplet accelerator 네트워크 연구
- **TSMC CoWoS-S/L 공식 WP** — interposer layer count / reticle 수치 원전 확인
- **Intel EMIB** — TSV 프리 embed bridge 방식의 최신 문서

---

## 결론

우리 논문의 novelty 3 축 (NL% predictor / warm-start RL / post-hoc fallback) 중 어느 하나도 위 12개 선행 연구의 어떤 조합에도 포함되지 않음. PARL 이 가장 가까우나 타깃 문제가 **multi-tenant interference (heterogeneous)** 라 우리 **single-tenant mean latency (homogeneous grid)** 와 **complementary**. Kite / Florets 는 adjacent-only 이므로 phantom load 의 구조적 원인을 제거하지 못함.

위 관계는 §II related work 와 Table~1 에 반영되어 있으며, 본 노트는 향후 rebuttal / camera-ready 시 각 수치/주장을 원문 재확인할 때의 출발점으로 사용한다.
