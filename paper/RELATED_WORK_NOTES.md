# Related Work Notes — Chiplet NoI Topology & Express Links

`paper/main.tex` 의 bibliography 에 실린 NoI 관련 선행 연구를 원문/공식 요약에서 직접 확인한 수치 중심으로 정리한 실무 노트. Rebuttal / camera-ready 시 cross-check 출발점.

## 표기 규약

- **[VERIFIED]**: 논문 원문(abstract/본문/공식 summary) 또는 venue page 에서 직접 확인한 사실·수치.
- **[CITATION-METADATA]**: 제목/저자/venue 만 확인, 본문 접근 불가.
- **[ACCESS-BLOCKED]**: 시도했으나 paywall/binary PDF 등으로 접근 실패. 원문 직접 확인 필요.
- **[VIA FIELD KNOWLEDGE]**: 분야 표준 상식 수준, 원문 재확인 권장.

---

## Tier 1: 직접 경쟁 또는 가장 가까운 선행

### PARL — Shukla et al., arXiv:2510.24113 (Oct 2025)

**"Taming the Tail: NoI Topology Synthesis for Mixed DL Workloads on Chiplet-Based Accelerators"**

- **저자** [VERIFIED]: Arnav Shukla, Harsh Sharma, Srikant Bharadwaj, Vinayak Abrol, Sujay Deb.
- **약어 출처** [VERIFIED]: "Partition-Aware Reinforcement Learner" (PARL).
- **RL 알고리즘** [VERIFIED]: **Maskable Proximal Policy Optimization (PPO)** with dynamic action masking. Mask 는 available physical port 가 없는 칩렛에 대한 link 추가 같은 illegal action 을 강제로 차단. Cold-start (strong baseline 으로부터의 warm-start 없음).
- **타깃 HW** [VERIFIED]: **AMD MI300X-class** 헤테로 패키지.
  - 8 XCD (compute) + 4 HBM3 (memory) + 2 IOD (I/O) = **14 chiplet**.
  - L2 cache 4 MB/XCD, shared Infinity Cache 256 MB (8 XCD 전체), HBM3 capacity 192 GB.
  - Memory cut 총 대역폭 **297.6 GB/s** (4 HBM-IOD nodes × 2 links × 37.2 GB/s).
- **Workload** [VERIFIED]: **Mixtral-8x7B**.
  - 32 layers, 임베딩 차원 d=4096, experts=8, **top-2 routing**.
  - Expert FFN footprint 256 MB per expert (W_FFN = 8 d² s).
  - Traffic class: expert weights (256 KB chunks), activations (log-normal 8 KB–1 MB), control metadata.
  - Multicast degree distribution Pr(D=1,2,4,8)=(0.55, 0.25, 0.15, 0.05).
  - Burstiness coefficient Ca²≈1.37.
- **Baseline** [VERIFIED]: **11 traditional/SoTA 토폴로지** (k-ary n-cubes 포함, HexaMesh 및 KITE 가 related work 에 언급).
- **핵심 수치 결과** [VERIFIED]:
  - Baseline mixed workload 에서 **4-5× throughput degradation** 으로 SLA 위반.
  - Interference Score 는 raw link count 와 상관 없음 (**R²≈0.15**).
  - Bottleneck link L48 에서 **p99 latency = 5.1 cycles** (under load).
  - PARL 생성 토폴로지: **worst-case slowdown을 1.2× 로 감소** (baseline >4× 대비).
  - Mean throughput 은 link-rich mesh 보다 다소 낮지만 IS 는 우수 — "maintains competitive mean throughput relative to link-rich meshes".
- **이론 도구** [VERIFIED]: Heavy-traffic 분석에 **Kingman's approximation** 사용: E[Wq] ≈ (ρ/(1−ρ)) · (Ca²+Cs²)/2 · (1/μ).
- **한계 (논문 명시 안 됨, 내재적 추정)** [VIA FIELD KNOWLEDGE]: Mixtral-8x7B 단일 모델 평가, 학습 iteration/convergence wall-clock 미공개, 칩렛 수 >16 스케일링 미검증, dynamic load-balancing 효과 누락.
- **우리와의 차이** (핵심 대비표):
  | Axis | PARL | Ours |
  |---|---|---|
  | Problem | Multi-tenant **interference** (tail) | Single-tenant **mean latency** |
  | Setup | Heterogeneous 14-chiplet (MI300X) | Homogeneous K=16/32 (R×C grid) |
  | Predictor | No | **NL% (ρ=0.744, τ=0.593 over 40 cells)** |
  | Warm-start | **No (cold Maskable PPO)** | **Yes (greedy allocator)** |
  | Safety | None | **≤ Greedy (post-hoc fallback)** |
  | Metric | IS, p99 | Mean latency saving |
- **Head-to-head reproduction 왜 안 했나** [VERIFIED from main.tex:71]: PARL 의 IS evaluator + multi-objective reward 를 BookSim 위에 재구현하는 비용이 큼. Qualitative positioning 으로 대체, ablation 의 cold-start 변종 RL 이 proxy.

---

### Kite — Bharadwaj et al., DAC 2020

**"Kite: A Family of Heterogeneous Interposer Topologies Enabled via Accurate Interconnect Modeling"**

- **저자** [VERIFIED]: Srikant Bharadwaj, Jieming Yin, et al. (전체 리스트 논문 PDF 헤더 기준).
- **가설**: Interposer 위의 long/short link 를 **정확하게 모델링** 하면 기존 Double Butterfly, Butter Donut 같은 토폴로지보다 나은 solution 이 있다.
- **Kite family** [VERIFIED]: Kite Small / Medium / Large — 각각 가장 긴 link 길이가 다름. Butter Donut / Kite Medium / Kite Large 는 long link 의 이득을 활용해 low latency.
- **도구** [VERIFIED]: **HeteroGarnet** 시뮬레이터 공개 (2020-06). NoC 와 NoI 가 서로 다른 clock frequency 에서 동작하는 것을 지원.
- **핵심 수치** [VERIFIED]: **7% latency 감소**, **17% max throughput 향상** — synthetic traffic 기준, **Double Butterfly** 및 **Butter Donut** 대비 평균 값.
- **Scope 한계** [VERIFIED from main.tex:65 + 논문 추론]: adjacent-and-chiplet-level topology optimization. Long link 을 일부 포함하나 **문제 설정상 interposer topology 선택** 이지, traffic-aware **express link 배치** 문제가 아님.
- **우리와의 차이**: Kite 는 **고정된 topology family** 를 제공, 우리는 **workload-adaptive express placement** 를 제안. 예측기/warm-start/fallback 축 모두 없음.

---

### Florets — Sharma et al., ACM TECS 2023 (vol. 22, no. 6)

**"Florets for Chiplets: Data Flow-aware High-Performance and Energy-efficient Network-on-Interposer for CNN Inference Tasks"**

- **저자** [VERIFIED]: Harsh Sharma, Lukas Pfromm, Rasit Onur Topaloglu, Janardhan Rao Doppa, Umit Y. Ogras, Ananth Kalyanaraman, Partha Pratim Pande.
- **수상** [VERIFIED]: **Best Paper Award at ESWEEK 2023**.
- **접근** [VERIFIED]: **Space-Filling Curve (SFC) 기반 NoI topology**. Data-flow pattern 과 task mapping 을 동시 최적화 해서 inter-chiplet data exchange 비용 감소.
- **핵심 수치** [VERIFIED]: 기존 SoTA NoI 대비 **latency 최대 58% 감소**, **energy 최대 64% 감소**. 데이터센터 규모 multi-CNN concurrent workload 기준.
- **우리와의 차이**: Florets 는 **CNN inference 전용** — traffic pattern 이 CNN data flow (주로 feature map + weight broadcast) 에 강하게 의존. 우리는 **LLM training traffic** (Tree AR, Hybrid TP+PP, MoE, Uniform) 을 타깃. 또한 Florets 는 topology family 선정이지 **예측기/warm-start/fallback** 이 없음.

---

### Modular Routing — Yin et al., ISCA 2018

**"Modular Routing Design for Chiplet-based Systems"**

- **저자** [VERIFIED]: Jieming Yin, Zhifeng Lin, Onur Kayiran, Matthew Poremba, Muhammad Shoaib Bin Altaf, Natalie Enright Jerger, Gabriel H. Loh.
- **Venue** [VERIFIED]: ISCA 2018, acceptance 64/373 = **17.2%**.
- **기여** [VERIFIED]: 각 chiplet 이 독자 NoC topology/routing 을 가지고 interposer 가 또 독자 topology/routing 을 가질 때, **deadlock-free 조합**을 보장하는 "몇 개의 turn restriction" 메카니즘. 결과적으로 시스템 전체 NoC+NoI 가 deadlock-free 로 합성 가능.
- **Media coverage** [VERIFIED]: IEEE Spectrum 에 소개됨.
- **우리와의 연결**: routing-level 독립성. 우리 paper 는 XY-style deterministic routing 을 가정하고, main.tex 의 "Routing Algorithm Independence" 논의 (§II/§III) 에서 Modular Routing 을 참고. Express link 는 routing algorithm 선택과 무관하게 phantom load 를 줄인다는 주장의 근거.

---

## Tier 2: NoC 고전 (intra-die express & concentrated)

### Express Virtual Channels (EVC) — Kumar et al., ISCA 2007

- **저자** [VERIFIED]: Amit Kumar, Li-Shiuan Peh, Partha Kundu, Niraj K. Jha (Kumar·Peh·Kundu·Jha).
- **DOI** [VERIFIED]: 10.1145/1250662.1250681.
- **아이디어** [VERIFIED]: NoC 의 **"virtual express lanes"** — 패킷이 dedicated VC 를 따라 distant node 사이 **intermediate router 를 bypass** 하여 이동. router arbitration/buffer 를 건너뜀.
- **구체 수치** [ACCESS-BLOCKED]: ISCA 2007 원문 (Berkeley PDF, ACM DL) 접근 실패 (binary PDF 및 ACM paywall). 원문 재확인 필요.
- **우리와의 차이** [VERIFIED from main.tex:68]: EVC 는 **monolithic NoC 내부** 배선 — wire delay 가 작고 optimization 타깃이 hop count. 우리는 **chiplet 외부 interposer wire** — die-edge PHY 와 interposer routing 자원 이라는 **물리 희소성** 이 주 제약. Express link 는 VC 같은 버퍼 메커니즘이 아니라 **물리적 direct wire**.

---

### Concentrated Mesh (C-Mesh) — Balfour & Dally, ICS 2006

**"Design Tradeoffs for Tiled CMP On-Chip Networks"**

- **저자** [VERIFIED]: James Balfour, William J. Dally.
- **핵심 아이디어** [VERIFIED]: **Concentrated mesh topology** + **replicated subnetworks** + **express channels** 를 조합.
- **핵심 수치** [VERIFIED]: 평가된 다른 네트워크 대비 **area 24% 향상, energy 48% 향상**. Second parallel network 추가로 performance 도 향상.
- **우리와의 차이** [VERIFIED from main.tex:68]: intra-die 단위 — tile 내부에서 여러 core 가 router 공유. chiplet 경계를 넘는 UCIe 점대점 제약이나 interposer wire 경합 문제와 무관.

---

## Tier 3: Chiplet 시스템 비용/평가 인프라

### Chiplet Actuary — Feng & Ma, DAC 2022 (arXiv:2203.12268)

**"Chiplet Actuary: A Quantitative Cost Model and Multi-Chiplet Architecture Exploration"**

- **저자** [VERIFIED]: Yinxiao Feng, Kaisheng Ma. (arXiv:2203.12268, DAC 2022.)
- **모델링 3개 통합 기술** [VERIFIED]:
  1. **MCM** (Multi-Chip Module) — organic substrate 기반.
  2. **InFO** (Integrated Fan-Out) — RDL 기반, chip-first/chip-last 변종.
  3. **2.5D CoWoS** — 실리콘 인터포저 기반 (chiplet + memory die).
- **모델 구성 요소** [VERIFIED]: RE cost 는 raw chip + package cost + defect waste + **KGD (Known Good Die) loss** + **D2D interface overhead** 를 포함. NRE 는 module design cost (재사용) 와 per-chip design cost 를 분리.
- **핵심 수치 결론** [VERIFIED]:
  - Advanced node 에서 multi-chip integration 으로 **die cost 최대 50% 절감** (yield 개선 덕).
  - Packaging overhead 는 총비용의 **30-50%** 차지 (복잡 통합일수록 크다).
  - Single-system-only 설계에서는 monolithic SoC 가 유리하며, **5nm 노드에서 생산량 > 2M unit** 부터 chiplet 이 유리.
  - Chiplet granularity 의 diminishing returns: **3-5 piece 이상 분할은 이득 체감**.
- **우리와의 연결**: §VI Physical Overhead 논의에서 "express link 은 interposer wire 자원을 소모" 라는 배경으로 인용 가능. 직접 수치 비교는 우리 범위 아님.
- **Open-source** [VERIFIED]: https://github.com/Yinxiao-Feng/DAC2022.

### CATCH — Graening et al., arXiv:2503.15753 (2025)

**"CATCH: a Cost Analysis Tool for Co-optimization of chiplet-based Heterogeneous systems"**

- **저자** [VERIFIED]: Alexander Graening, Jonti Talukdar, Saptadeep Pal, Krishnendu Chakrabarty, Puneet Gupta.
- **Scope** [VERIFIED]: **2.5D 와 3D 적층** 모두 포함. 다양한 configuration 과 제조 공정 파라미터 반영.
- **Case study 관점** [VERIFIED]: chip size, defect density, test cost, IO types, assembly process, substrate 전반.
- **구체 수치** [ACCESS-BLOCKED]: arXiv abstract 페이지에서 수치 extract 실패. 원문 재확인 필요.
- **Chiplet Actuary 와의 차이** [ACCESS-BLOCKED]: 두 논문을 나란히 비교한 summary 를 공개 abstract 에서 확인 못함. Actuary 보다 후발이며 tool 로서 공개된 점은 확실.

### CPElide — Dalmia, Kumar, Sinclair, MICRO 2024

**"CPElide: Efficient Multi-Chiplet GPU Implicit Synchronization"**

- **저자** [VERIFIED]: Preyesh Dalmia, Rajesh Shashi Kumar, Matthew D. Sinclair.
- **Venue** [VERIFIED]: MICRO 2024 (Austin, TX).
- **핵심 아이디어** [VERIFIED]: Heterogeneous system 의 embedded command processor 를 이용해 **inter-chiplet data dependency 를 추적**, 불필요한 implicit synchronization 을 **elide**. 대조군은 보수적 HMG.
- **구현 구조** [VERIFIED]: **Chiplet Coherence Table** (global command processor 의 private memory 내). 각 row = (data structure base address, address range per chiplet, access mode, chiplet access bit-vector).
- **핵심 수치** [VERIFIED]: **24 workload** 에서 평균:
  - Performance **+13% / +19%** (vs current / vs HMG)
  - Energy **-14% / -11%**
  - Network traffic **-14% / -17%**.
- **공개** [VERIFIED]: gem5 기반 multi-chiplet 모델 — https://github.com/hal-uw/gem5-multiChiplet-micro24.
- **우리와의 연결**: traffic 의 상당 부분이 synchronization 으로부터 나온다는 관점 → tree_allreduce workload 가 synchronous barrier-driven 이라는 우리 modeling 의 현실성 지지.

### CnSim (Chiplet Network Simulator) — Feng et al., USENIX ATC 2024

**"Evaluating Chiplet-based Large-Scale Interconnection Networks via Cycle-Accurate Packet-Parallel Simulation"**

- **저자** [VERIFIED]: Yinxiao Feng, Yuchen Wei, Dong Xiang, Kaisheng Ma (Tsinghua IIIS).
- **핵심** [VERIFIED]: **Packet-centric simulation architecture** + **atomic-based hyper-threading**. 대규모 chiplet 네트워크를 cycle-accurate 로 시뮬하면서 속도 확보.
- **수치** [VERIFIED]: 기존 cycle-accurate simulator 대비 **11×–14× speedup**.
- **Open-source** [VERIFIED]: https://github.com/Yinxiao-Feng/chiplet-network-sim.
- **우리 선택**: 재현성과 기존 baseline 호환을 위해 BookSim 2.0 + anynet topology 를 사용. CnSim 은 향후 cross-validation 후보.

### BookSim 2.0 — Jiang et al., ISPASS 2013

- **저자** [VERIFIED from main.tex:549]: Nan Jiang et al.
- **Venue** [VERIFIED]: ISPASS 2013.
- **역할** [VERIFIED]: 우리 BookSim 실험의 기반 시뮬레이터. `anynet` topology 로 임의의 그래프 구조 (mesh + express link) 를 표현 가능 — 우리 express placement 실험의 필수 조건.

---

## Tier 4: 표준 / 하드웨어 레퍼런스

### UCIe — Das Sharma et al., IEEE Micro 2024 + UCIe Consortium Spec

**"UCIe: Standard for an Open Chiplet Ecosystem"**

- **표준 버전별 특징** [VERIFIED from uciexpress.org spec page]:
  - **UCIe 1.0**: foundation — D2D PHY, protocol stack, software model, compliance test.
  - **UCIe 1.1**: multiprotocol support, automotive health monitoring, reduced-cost bump map.
  - **UCIe 2.0**: manageability (UDA), **3D packaging with hybrid bonding (1–25 μm pitch)** 지원, DFx.
  - UCIe 3.0 (2025 발표): bandwidth 2× 확대.
- **Data rate (per lane)** [VERIFIED]:
  - UCIe 2.0: **32 GT/s**.
  - UCIe 3.0: **48 GT/s 또는 64 GT/s**.
- **Advanced vs Standard Package** [VIA FIELD KNOWLEDGE + spec page]: Advanced = silicon interposer / silicon bridge (UCIe-A) 로 고밀도 bump; Standard = organic substrate (UCIe-S) 로 저비용. 세부 bump pitch 는 원문 재확인 필요.
- **Point-to-point 제약** [VERIFIED from main.tex:103]: UCIe 1.x / 2.0 PHY 는 **strictly point-to-point** — on-interposer switching fabric 은 표준상 허용 안 됨. 이것이 우리가 "switch topology (예: FBfly with shared router) 대신 direct wire express" 를 쓰는 근거.
- **Beachfront density (GB/s/mm)** [ACCESS-BLOCKED]: UCIe 공식 spec page 에 숫자 없음. 원문 IEEE Micro 논문 재확인 필요.
- **BER 요구사항** [ACCESS-BLOCKED]: 동일.

### NVIDIA Blackwell — Technical Brief 2024

- [CITATION-METADATA] NVIDIA 공식 brief.
- [VIA FIELD KNOWLEDGE] B200: 2-die package, NVLink-C2C 기반 die-to-die.
- 우리 intro 의 "chiplet count 증가 중" motivation 레퍼런스.

### AMD MI300X — Smith et al., Hot Chips 2024

- [CITATION-METADATA] Hot Chips 2024.
- [VERIFIED via PARL paper 인용 추적]: 8 XCD (compute) + 4 HBM3 (memory) + 2 IOD (I/O) = 14 chiplet 헤테로 패키지, CoWoS 기반 2.5D. Memory cut 297.6 GB/s (4 × 2 × 37.2 GB/s).

---

## 우리 논문과의 비교 요약 (Table 1 확장판, 6축)

| Work | Target Problem | Predictor? | Warm-start? | Safety Guarantee | Target Workload | Key Numeric Claim |
|---|---|---|---|---|---|---|
| Kite (DAC '20) | Topology family | No | N/A | — | Synthetic NoI | +7% lat, +17% thru vs Double Butterfly / Butter Donut |
| Florets (TECS '23) | Data-flow aware NoI | No | N/A | — | CNN inference | -58% lat, -64% energy vs SoTA NoI |
| Modular Routing (ISCA '18) | Deadlock-free routing | No | N/A | — | Generic | N/A (qualitative method) |
| PARL (arXiv '25) | Multi-tenant interference | No | **No (cold Maskable PPO)** | None | Mixtral-8x7B on MI300X-class | Worst-case slowdown 1.2× (vs baseline >4×) |
| EVC (ISCA '07) | Intra-die bypass | No | N/A | — | Generic NoC | (access blocked) |
| C-Mesh (ICS '06) | Tiled CMP NoC | No | N/A | — | Generic NoC | -24% area, -48% energy |
| Chiplet Actuary (DAC '22) | Cost model | N/A | N/A | N/A | 2.5D/MCM/InFO | -50% die cost, monolithic wins <2M unit@5nm |
| CPElide (MICRO '24) | Implicit sync elide | No | N/A | — | GPU (24 wl) | +13-19% perf, -14-17% traffic |
| CnSim (ATC '24) | Simulator infra | N/A | N/A | N/A | N/A | 11-14× speedup |
| **Ours** | **Express placement** | **NL% (ρ=0.744, τ=0.593, 40 cells)** | **Yes (greedy)** | **≤ Greedy (post-hoc fallback)** | **LLM training (Tree/Hybrid/MoE/Uniform)** | **+28.1% mean, max +56.4% (vs adj-only)** |

---

## Paper 에서 우리가 직접 인용/주장하는 수치 (cross-check용)

- [VERIFIED from main.tex:148] α_max = √K · ⌊K/4⌋ = Θ(K^{3/2}) — 정사각형 K 그리드 center-link amplification.
- [VERIFIED from main.tex:103] Interposer signal layer 수: **3–6 layers** (현 세대 CoWoS-class).
- [VERIFIED from main.tex:103] Reticle-bounded interposer area: **≤ 2500 mm²**.
- [VERIFIED from main.tex:475] Express link wire-delay model: **distance d 에 대해 2d cycle**.
- [VERIFIED from main.tex:475] λ-sensitivity (wire delay scaling) 12-cell 결과:
  - Tree AR +17.7% → +14.3% (λ=1.0→2.0)
  - Hybrid TP+PP +47.5% → +41.9%
  - Uniform Random +46.9% → +42.3%
  - MoE Skewed +56.5% → +52.5%
- [VERIFIED from main.tex:71] Cold RL worst-case vs greedy: **+11.3%**. Warm-start: **+1.7% before fallback, +0.0% after fallback**.

---

## 접근 실패 / 재확인 필요 항목 (후속 작업)

| 항목 | 현재 상태 | 필요 조치 |
|---|---|---|
| EVC (ISCA '07) 구체 수치 | [ACCESS-BLOCKED] Berkeley PDF binary, ACM DL paywall | 학교 라이브러리 via proxy 접근 |
| C-Mesh 추가 수치 (baseline 명세) | [VERIFIED 24%/48% 만] | Stanford CVA 직접 다운로드 |
| UCIe beachfront density, BER | [ACCESS-BLOCKED] IEEE Micro 본문 paywall | IEEE Xplore 접근 |
| CATCH 구체 수치 | [ACCESS-BLOCKED] arXiv abstract 만 | arXiv PDF HTML 버전 |
| Modular Routing 구체 turn restriction | [VERIFIED method 수준] | 논문 §4 읽기 |
| Kite 내 long link 처리 방식 | [VERIFIED latency/throughput 결과만] | 논문 PDF 재검토 |
| PARL 구체 training setup | [VERIFIED workload/HW 수준] | arXiv PDF 재fetch (binary 실패) |

---

## 아직 bibliography 에 없지만 서베이에 추가 후보

- **HexaMesh** — PARL 에 언급됨, chiplet topology 변종.
- **PlaceIT** (ETH Zürich, 2025) — placement-based inter-chiplet interconnect topologies.
- **Chiplet Placement and Routing with Neural Solver** (NeurIPS ML for Systems 2024).
- **"Survey of chiplet-based integrated architecture"** (Science China IS, 2023) — EDA 관점 서베이.

---

## 결론

우리 논문의 novelty 3 축 (**NL% predictor / warm-start RL / post-hoc fallback**) 중 어느 하나도 위 13개 선행 연구의 어떤 조합에도 포함되지 않음. PARL 이 가장 가까우나 타깃 문제가 **multi-tenant interference (heterogeneous MI300X, Mixtral-8x7B, tail latency)** 라 우리 **single-tenant mean latency (homogeneous K=16/32 grid, 4 LLM workload)** 와 **complementary**. Kite / Florets / C-Mesh / EVC 모두 **express link placement 문제** 는 다루지 않음. Chiplet Actuary / CATCH 는 cost model, CPElide 는 sync elide, CnSim/BookSim 은 infra — **문제 설정 자체가 다름**.

본 노트는 rebuttal 시 각 수치/주장 재검증 출발점이며, [ACCESS-BLOCKED] 항목은 venue proxy 또는 물리 library 접근으로 camera-ready 전 해소 필요.
