@echo off
setlocal enabledelayedexpansion
REM 프로젝트 루트에서 실행하세요.
REM 예: samples\architecture\scripts\run_architecture_samples.bat

set TEMPLATE=templates\arch_template.docx
if not exist "%TEMPLATE%" (
  echo 템플릿을 찾을 수 없습니다: %TEMPLATE%
  echo 프로젝트 루트에서 실행했는지 확인하세요.
  exit /b 1
)

call :RUN_ONE 01 samples\architecture\requirements\requirements.01_ai_sdlc.json samples\architecture\infra\infra_spec.01_fastapi_sdlc.json
call :RUN_ONE 02 samples\architecture\requirements\requirements.02_public_portal.json samples\architecture\infra\infra_spec.02_spring_public_portal.json
call :RUN_ONE 03 samples\architecture\requirements\requirements.03_data_platform.json samples\architecture\infra\infra_spec.03_node_data_platform.json
call :RUN_ONE 04 samples\architecture\requirements\requirements.04_lms_campus.json samples\architecture\infra\infra_spec.04_django_lms.json
call :RUN_ONE 05 samples\architecture\requirements\requirements.05_finance_internal.json samples\architecture\infra\infra_spec.05_egov_finance_internal.json

echo.
echo 전체 샘플 생성 완료
exit /b 0

:RUN_ONE
set IDX=%~1
set REQ=%~2
set INFRA=%~3
set OUTDIR=_arch_lab_sample_%IDX%
echo.
echo ==============================
echo ARCH SAMPLE %IDX%
echo requirements: %REQ%
echo infra       : %INFRA%
echo outdir      : %OUTDIR%
echo ==============================
python run_architecture_agent.py "%REQ%" --arch-config "%INFRA%" --out-dir "%OUTDIR%"
python render_arch_docx.py "%OUTDIR%\document.json" --structure "%OUTDIR%\structure.json" --template "%TEMPLATE%" --out "%OUTDIR%\architecture.docx"
echo 생성 완료: %OUTDIR%\architecture.docx
exit /b 0
