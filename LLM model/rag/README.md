
## Retrieval-Augmented Generation (RAG) 아키텍처


### 개요

RAG(Retrieval-Augmented Generation)는 산출물 생성 전에 요구사항 기준서, DB 표준 정보, UI/UX 가이드 등의 기준 문서를 벡터화하여 Qdrant Vector DB에 저장한다.

산출물 생성 시 각 Agent는 목적에 맞는 검색 Query를 생성하고, 관련 문서를 검색하여 LLM Prompt Context에 주입한다. 이를 통해 생성 결과의 **표준성(Standardization)**, **근거성(Traceability)**, **일관성(Consistency)** 을 향상시킨다.

---

### Vector DB Collection 구성

| Collection | 저장 데이터 | 목적 |
|------------|------------|------|
| Requirement Collection | 요구사항 기준서, 유사 요구사항, 참고 문서 | 요구사항 생성 품질 향상 |
| ERD / DB Standard Collection | 테이블명, 컬럼명, 도메인, 표준용어 | 데이터 모델 표준화 |
| Interface UI/UX Collection | 화면 설계 기준, UI/UX 가이드 | 인터페이스 일관성 확보 |

---

<img width="1024" height="1536" alt="LLM_RAG flow" src="https://github.com/user-attachments/assets/cbd4d0dd-4d8c-47e3-a4e6-daa3a1dff2e3" />


### Agent별 검색 전략

#### 요구사항 정의서 Agent

RFP 및 회의록을 분석하여 요구사항 생성에 필요한 기준 문서를 검색한다.

**검색 대상**

- 요구사항 표준
- 유사 프로젝트 요구사항
- 기능 요구사항
- 비기능 요구사항
- 공통 요구사항
- 요구사항 작성 가이드

**활용 목적**

- 요구사항 누락 방지
- 유사 사례 기반 품질 향상

---

#### ERD / DB 설계 Agent

데이터 모델링 시 공공기관 표준 DB 기준을 검색한다.

**검색 대상**

- 표준 테이블명
- 표준 컬럼명
- 데이터 도메인
- 데이터 사전

**활용 목적**

- 데이터 표준 준수
- 컬럼명 일관성 확보
- ERD 품질 향상

---

#### 인터페이스 설계 Agent

화면 분석 결과와 요구사항을 기반으로 UI/UX 가이드를 검색한다.

**검색 대상**

- UI 설계 가이드
- UX 원칙
- 화면 구성 패턴
- 접근성 기준
- 컴포넌트 표준

**활용 목적**

- 사용자 경험 향상
- 화면 설계 일관성 확보
- UI 표준 적용

---

### Context 생성

각 Agent의 검색 결과는 Score, Text, Document Type, Metadata 형태로 구성되며 LLM Prompt에 함께 주입된다.

검색된 Context는 산출물 생성 과정에서 참고 근거로 활용되어 생성 결과의 품질과 신뢰성을 향상시킨다.

---

### 기대 효과

- 표준 문서 기반 산출물 생성
- 요구사항 품질 향상
- 데이터 모델 표준 준수
- UI/UX 일관성 확보
- 생성 결과의 근거성 및 추적성 확보
- Hallucination 감소
- Agent별 전문성 강화
