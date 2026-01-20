import sys
import traceback
import os
import glob

# 버전 확인용 출력 (빌드 갱신 확인)
print("\n" + "="*30)
print("   Worknet Crawler v3.1   ")
print("   Updated: Browser Fix   ")
print("="*30 + "\n")

# [중요] PyInstaller 실행 시 브라우저 경로 문제 해결
# 임시 폴더(_MEI...)가 아닌 사용자 로컬 경로의 브라우저를 사용하도록 강제 설정
# (환경변수 설정과 더불어, 아래에서 직접 경로주입도 수행함)
MS_PLAYWRIGHT_PATH = os.path.join(os.getenv("LOCALAPPDATA"), "ms-playwright")
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = MS_PLAYWRIGHT_PATH

# 전역 예외 처리 설정을 위한 로그 파일 경로
LOG_FILE = "debug_launch_log.txt"

def log_error(msg):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except:
        pass

def find_chromium_executable():
    """
    로컬 AppData의 ms-playwright 폴더에서 chromium 실행 파일을 직접 찾습니다.
    PyInstaller 환경에서 경로 인식이 실패하는 것을 방지합니다.
    """
    try:
        print("[초기화] 브라우저 경로 자동 탐색 중...")
        local_app_data = os.getenv("LOCALAPPDATA")
        if not local_app_data:
             print("[오류] LOCALAPPDATA 환경변수가 없습니다.")
             return None
             
        ms_playwright_path = os.path.join(local_app_data, "ms-playwright")
        print(f"  - 검색 위치: {ms_playwright_path}")
        
        if not os.path.exists(ms_playwright_path):
            print("  - [오류] ms-playwright 폴더가 없습니다. 'playwright install'이 필요할 수 있습니다.")
            return None
            
        # 모든 chromium 폴더 검색
        search_pattern = os.path.join(ms_playwright_path, "chromium-*")
        dirs = glob.glob(search_pattern)
        print(f"  - 검색된 폴더: {[os.path.basename(d) for d in dirs]}")
        
        # 최신 버전부터 확인 (역순 정렬)
        for d in sorted(dirs, reverse=True):
            exe_path = os.path.join(d, "chrome-win", "chrome.exe")
            if os.path.exists(exe_path):
                print(f"  - [성공] 브라우저 발견: {exe_path}")
                return exe_path
                
        print("  - [실패] 유효한 chrome.exe를 찾을 수 없습니다.")
        return None
            
    except Exception as e:
        log_error(f"Error finding chromium: {traceback.format_exc()}")
        print(f"  - [예외] 브라우저 탐색 중 오류: {e}")
        return None

try:
    import asyncio
    import json
    import re
    import random
    import pandas as pd
    from playwright.async_api import async_playwright
except Exception:
    log_error(traceback.format_exc())
    print("임포트 에러 발생! debug_launch_log.txt를 확인하세요.")
    input("Press Enter to exit...")
    sys.exit(1)

# 텍스트 정제 함수
def clean_text(text):
    if not isinstance(text, str):
        return str(text)
    text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F]', '', text)
    if len(text) > 32000:
        text = text[:32000] + "..."
    return text

async def run():
    # [중요] 사용 할 브라우저 경로 미리 찾기
    exec_path = find_chromium_executable()
    
    if not exec_path:
        print("\n" + "="*50)
        print("[치명적 오류] 실행할 수 있는 브라우저를 찾지 못했습니다.")
        print("프로그램이 'C:\\Users\\<사용자>\\AppData\\Local\\ms-playwright' 경로에서")
        print("Chromium 브라우저를 찾을 수 없습니다.")
        print("해결법: 터미널에서 'playwright install chromium'을 실행해주세요.")
        print("="*50 + "\n")
        # 여기서 종료해야 엉뚱한 임시 경로 에러를 피할 수 있음
        return

    async with async_playwright() as p:
        # headless=False: 브라우저가 뜨고 작동하는 모습을 볼 수 있음
        
        launch_args = {
            "headless": False,
            "args": ["--disable-blink-features=AutomationControlled"],
            "executable_path": exec_path  # 찾은 경로 강제 지정
        }
        
        print(f"브라우저 실행 시도: {exec_path}")
        try:
            browser = await p.chromium.launch(**launch_args)
        except Exception as e:
            print(f"[브라우저 실행 실패] {e}")
            raise e
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            # 화면 크기 넉넉하게
            viewport={'width': 1600, 'height': 900}
        )
        
        # navigator.webdriver = false 설정 (탐지 우회)
        await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # [속도 개선] 이미지, 폰트 등 불필요한 리소스 로딩 차단
        await context.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,eot}", lambda route: route.abort())

        page = await context.new_page()

        url = "https://www.work24.go.kr/wk/a/b/1200/retriveDtlEmpSrchList.do"
        print(f"이동 중: {url}...")
        
        try:
            await page.goto(url, wait_until="networkidle")
        except Exception as e:
            print(f"이동 오류(1차): {e}")
            await asyncio.sleep(1) # 대기 시간 단축
            try:
                await page.goto(url)
                await page.wait_for_load_state("domcontentloaded")
            except Exception as e2:
                print(f"이동 오류(2차): {e2} - 접속이 차단되었거나 인터넷 연결을 확인해주세요.")
                # 여기서 종료하지 않고 진행 시도하거나 return 할 수 있음

        jobs = []
        target_count = 100 
        page_num = 1
        
        # [속도 최적화] 병렬 작업을 위한 설정
        # 동시에 12개 탭까지 허용 (검색 속도 대폭 증가)
        sem = asyncio.Semaphore(12)
        tasks = []
        scheduled_count = 0

        # 상세 페이지 수집 및 브라우저 닫기까지 처리하는 비동기 함수
        async def extract_detail(dtl_page, job_basic):
            async with sem:
                try:
                    # 로딩 대기
                    await dtl_page.wait_for_load_state("domcontentloaded")
                    await asyncio.sleep(0.3) # 대기 시간 최소화

                    # [중요] '기업정보' 탭이나 버튼이 있다면 클릭하여 정보 로딩 유도
                    try:
                        # "기업정보" 텍스트를 가진 탭/버튼 찾기 (상단 탭 또는 중간 버튼)
                        corp_tab = dtl_page.locator("a:has-text('기업정보'), li:has-text('기업정보'), button:has-text('기업정보')").first
                        if await corp_tab.count() > 0:
                            if await corp_tab.is_visible():
                                await corp_tab.click()
                                await asyncio.sleep(0.5) # 로딩 대기
                    except:
                        pass

                    industry = "정보 없음"
                    employees = "정보 없음"
                    fax = "정보 없음"
                    address = "정보 없음"

                    # 메인 페이지 및 모든 iframe 탐색
                    frames = [dtl_page] + dtl_page.frames

                    for frame in frames:
                        try:
                            # 1. 업종
                            if industry == "정보 없음":
                                # Case A: 표 형식 (th, td)
                                th = frame.locator("th").filter(has_text=re.compile(r"업\s*종"))
                                if await th.count() > 0:
                                    td = th.first.locator("xpath=following-sibling::td")
                                    if await td.count() > 0:
                                        industry = await td.first.inner_text()
                                        industry = industry.strip()
                                
                                # Case B: 리스트 형식 (li > em.tit)
                                if industry == "정보 없음":
                                    # <em class="tit">업종</em>노인 요양 복지시설 운영업
                                    em = frame.locator("li em.tit").filter(has_text=re.compile(r"업\s*종"))
                                    if await em.count() > 0:
                                        # em의 부모(li) 텍스트 전체에서 em 텍스트('업종')를 제거하는 방식
                                        li = em.first.locator("xpath=..")
                                        full_text = await li.inner_text() # "업종\n노인 요양..."
                                        # em 텍스트 제거하고 나머지 반환
                                        industry = full_text.replace(await em.first.inner_text(), "").strip()

                            # 2. 인원수 (근로자수 / 사원수)
                            if employees == "정보 없음":
                                # Case A: 표 형식
                                th = frame.locator("th").filter(has_text=re.compile(r"(근로자수|사원수|직원수)"))
                                if await th.count() > 0:
                                    td = th.first.locator("xpath=following-sibling::td")
                                    if await td.count() > 0:
                                        employees = await td.first.inner_text()
                                        employees = employees.strip()
                                
                                # Case B: 리스트 형식
                                if employees == "정보 없음":
                                     em = frame.locator("li em.tit").filter(has_text=re.compile(r"(근로자수|사원수|직원수)"))
                                     if await em.count() > 0:
                                        li = em.first.locator("xpath=..")
                                        full_text = await li.inner_text()
                                        employees = full_text.replace(await em.first.inner_text(), "").strip()

                            # 3. 팩스
                            if fax == "정보 없음":
                                th = frame.locator("th").filter(has_text=re.compile(r"(팩스|FAX|Fax)"))
                                if await th.count() > 0:
                                    td = th.first.locator("xpath=following-sibling::td")
                                    if await td.count() > 0:
                                        fax = await td.first.inner_text()
                                        fax = fax.strip()
                            
                            # 4. 주소 (회사주소 / 소재지)
                            if address == "정보 없음":
                                # [최우선] Case Special: 지도 버튼(data-addr) 활용
                                # 예: <button data-addr="충청북도 제천시...">
                                try:
                                    map_attr_el = frame.locator("[data-addr]").first
                                    if await map_attr_el.count() > 0:
                                        val = await map_attr_el.get_attribute("data-addr")
                                        if val and len(val.strip()) > 5:
                                            address = val.strip()
                                except: pass

                                # Case A: 표 형식 (th -> td)
                                if address == "정보 없음":
                                    th = frame.locator("th").filter(has_text=re.compile(r"(주소|소재지|위치)"))
                                    if await th.count() > 0:
                                        td = th.first.locator("xpath=following-sibling::td")
                                        if await td.count() > 0:
                                            address = await td.first.inner_text()
                                            address = address.strip()
                                
                                # Case B: 리스트 형식 (li > em.tit)
                                if address == "정보 없음":
                                     em = frame.locator("li em.tit").filter(has_text=re.compile(r"(주소|소재지|위치)"))
                                     if await em.count() > 0:
                                        li = em.first.locator("xpath=..")
                                        full_text = await li.inner_text()
                                        address = full_text.replace(await em.first.inner_text(), "").strip()

                                # Case C: 텍스트로 바로 적혀있는 경우 (P, DIV 등)
                                # 예: <p>경기도 양주시 ...</p>
                                if address == "정보 없음":
                                    regions = ["서울", "경기", "인천", "부산", "대구", "광주", "대전", "울산", "세종", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
                                    invalid_keywords = ["연봉", "급여", "월급", "일급", "시급", "채용", "모집", "근무", "우대", "경력", "만원", "찾아줘"]
                                    
                                    for region in regions:
                                        # 해당 지역명으로 시작하는 P, DIV 태그 검색
                                        xpath_query = f"//p[starts-with(normalize-space(.), '{region}')] | //div[starts-with(normalize-space(.), '{region}')] | //span[starts-with(normalize-space(.), '{region}')]"
                                        addr_el = frame.locator(xpath_query).first
                                        if await addr_el.count() > 0:
                                            cand_addr = await addr_el.inner_text()
                                            cand_addr = re.sub(r'\s+', ' ', cand_addr).strip()
                                            
                                            # [필터링] 주소가 아닌 문장(연봉, 채용 등) 걸러내기
                                            if any(k in cand_addr for k in invalid_keywords):
                                                continue

                                            # 너무 긴 문장(본문 등)은 제외하고 적당한 길이인 경우만 주소로 인식
                                            if 5 < len(cand_addr) < 80:
                                                address = cand_addr
                                                break

                        except:
                            continue

                    # 3-2. 팩스 (Regex - 테이블에서 못 찾은 경우)
                    if not fax or fax == "정보 없음" or fax == "-":
                         try:
                            all_text = ""
                            for frame in frames:
                                try: all_text += await frame.content()
                                except: pass
                            
                            pattern = re.compile(r'(?:팩스|FAX|Fax|F\s*A\s*X)(?:<[^>]*>|[\s:.-])*(\d{2,4}[-. ]\d{3,4}[-. ]\d{4})')
                            match = pattern.search(all_text)
                            if match:
                                found_num = match.group(1).replace(" ", "").replace(".", "-")
                                if not found_num.startswith("010"):
                                    fax = found_num
                         except:
                             pass
                    
                    # 4-2. 주소 (Regex - 테이블/리스트/엘리먼트에서 못 찾은 경우)
                    if address == "정보 없음":
                         try:
                            all_plain_text = ""
                            for frame in frames:
                                try: all_plain_text += await frame.inner_text() + "\n"
                                except: pass
                            
                            # 광역자치단체로 시작하는 주소 패턴
                            addr_pattern = re.compile(r'((?:서울|경기|인천|부산|대구|광주|대전|울산|세종|강원|충북|충남|전북|전남|경북|경남|제주)[가-힣\s\d,.-]+(?:로|길|동|가|읍|면|리)\s*[\d-]+(?:[,]\s*[가-힣\d\s,.-]+)?)')
                            match = addr_pattern.search(all_plain_text)
                            if match:
                                found_addr = match.group(0).strip()
                                found_addr = re.sub(r'\s+', ' ', found_addr)
                                
                                # [필터링] 주소가 아닌 문장 걸러내기
                                invalid_keywords = ["연봉", "급여", "월급", "일급", "시급", "채용", "모집", "근무", "우대", "경력", "만원", "찾아줘"]
                                if not any(k in found_addr for k in invalid_keywords):
                                    if len(found_addr) < 80:
                                        address = found_addr
                         except:
                             pass

                    # 데이터 병합
                    job_basic.update({
                        "industry": industry,
                        "employees": employees,
                        "fax": fax,
                        "address": address
                    })
                    jobs.append(job_basic)
                    
                    print(f"  [수집 완료] {job_basic['title'][:15]}... | 주소: {address} | 팩스: {fax}")

                except Exception as e:
                    print(f"  [상세 과정 오류] {e}")
                finally:
                    # 탭 닫기
                    try: await dtl_page.close()
                    except: pass

        while scheduled_count < target_count:
            print(f"\n--- {page_num}페이지 탐색 중 (수집 예정: {scheduled_count}, 완료: {len(jobs)}) ---")
            
            # 리스트 로딩 대기
            try:
                await page.wait_for_selector('tr[id^="list"]', state="attached", timeout=5000)
            except:
                print("이 페이지에서 리스트 아이템을 찾을 수 없습니다.")
                break
            
            # 인덱스로 접근하여 순차 처리 (하나 찾고, 들어가고, 다음꺼 찾고..)
            list_rows = page.locator('tr[id^="list"]')
            count = await list_rows.count()
            print(f"이 페이지 목록 개수: {count}개")
            
            if count == 0:
                break

            for i in range(count):
                if scheduled_count >= target_count:
                    break
                
                try:
                    row = list_rows.nth(i)
                    
                    # --- 기본 정보 추출 (동기) ---
                    # 제목
                    title_el = row.locator('a.t3_sb') 
                    if await title_el.count() == 0: title_el = row.locator('td.link a').first
                    title = await title_el.text_content() if await title_el.count() > 0 else "N/A"
                    title = title.strip()
                    
                    # 회사명
                    company_el = row.locator('.cp_name')
                    company = await company_el.text_content() if await company_el.count() > 0 else "N/A"
                    company = company.strip()

                    # 급여
                    salary = "N/A"
                    salary_el = row.locator('li.dollar span.item.b1_sb')
                    s_count = await salary_el.count()
                    if s_count > 0:
                        salary_parts = []
                        for si in range(s_count):
                            t = await salary_el.nth(si).text_content()
                            if t: salary_parts.append(t.strip())
                        salary = " / ".join(salary_parts)
                        salary = re.sub(r'\s+', ' ', salary).strip()

                    # 지역
                    location = "N/A"
                    loc_el_p = row.locator('li.site p')
                    if await loc_el_p.count() > 0: location = await loc_el_p.text_content()
                    else:
                        loc_el = row.locator('li.site')
                        if await loc_el.count() > 0: location = await loc_el.text_content()
                    location = location.strip()

                    # 근무시간
                    time_el = row.locator('li.time')
                    time_info = await time_el.text_content() if await time_el.count() > 0 else "N/A"
                    time_info = time_info.strip()

                    # 기본 데이터 패키징
                    job_basic = {
                        "title": title,
                        "company": company,
                        "salary": salary,
                        "location": location,
                        "schedule": time_info
                    }

                    # --- 상세 페이지 탭 열기 (직렬) ---
                    # 탭 열기는 순차적으로 해야 안전하게 핸들링 가능
                    detail_page = None
                    try:
                        async with context.expect_page(timeout=5000) as new_page_info:
                            await title_el.click(modifiers=["Control"])
                        detail_page = await new_page_info.value
                    except:
                        print(f"  [Skip] 클릭 실패 또는 탭 안 열림: {title}")
                        continue
                    
                    if detail_page:
                        # [병렬 처리 핵심] 태스크 생성 후 백그라운드로 넘김
                        # extract_detail 함수가 알아서 수집하고 jobs에 넣고 탭을 닫음
                        task = asyncio.create_task(extract_detail(detail_page, job_basic))
                        tasks.append(task)
                        scheduled_count += 1
                        print(f"  [작업 예약] {title[:10]}... (탭 오픈)")

                        # 탭 오픈 간격 (빠른 처리)
                        await asyncio.sleep(random.uniform(0.4, 0.8))
                    
                except Exception as e:
                    print(f"행 처리 중 오류: {e}")
                    continue
            
            # 목표 달성 체크
            if scheduled_count >= target_count:
                print("목표 수집 개수만큼 예약을 완료했습니다.")
                break

            # 다음 페이지 이동
            next_button = page.locator('.btn_page.next')
            if await next_button.count() > 0:
                print(">> 다음 페이지로 이동...")
                await next_button.click()
                try: await page.wait_for_load_state("networkidle", timeout=5000)
                except: pass
                await asyncio.sleep(2) 
                page_num += 1
            else:
                print("다음 버튼이 없거나 리스트의 끝입니다.")
                break
        
        # 모든 상세 페이지 작업이 완료될 때까지 대기
        print("\n모든 상세 페이지 수집 작업이 완료되기를 기다리는 중...")
        await asyncio.gather(*tasks)
        
        # [중요] 진행 중인 모든 백그라운드 태스크가 끝날 때까지 대기
        if tasks:
            print(f"\n남은 {len([t for t in tasks if not t.done()])}개의 상세 수집 작업을 기다리는 중...")
            await asyncio.gather(*tasks, return_exceptions=True)

        # 파일 저장
        print(f"\n수집 완료: 총 {len(jobs)} 건.")
        df = pd.DataFrame(jobs)
        
        # 컬럼명 한글로 변경
        df.rename(columns={
            "title": "채용공고명",
            "company": "업체명",
            "industry": "업종",
            "employees": "인원수",
            "fax": "팩스번호",
            "address": "주소",
            "salary": "급여",
            "location": "지역",
            "schedule": "근무시간"
        }, inplace=True)

        print("데이터 정제 중...")
        for col in df.columns:
            df[col] = df[col].apply(clean_text)

        try:
            df.to_excel('worknet_results.xlsx', index=False, engine='openpyxl')
            print(f"\n결과를 worknet_results.xlsx 파일로 저장했습니다.")
        except PermissionError:
             print("\n[중요] 엑셀 파일이 열려있어서 저장에 실패했습니다. 파일을 닫고 다시 실행해주세요.")
             try:
                 df.to_excel('worknet_results_backup.xlsx', index=False, engine='openpyxl')
                 print("대신 worknet_results_backup.xlsx 파일로 저장했습니다.")
             except:
                 pass

        await browser.close()

if __name__ == "__main__":
    try:
        # 윈도우 실행 파일 디버깅을 위한 로그 파일 생성
        with open("debug_start_check.txt", "w", encoding="utf-8") as f:
            f.write("프로그램 시작...\n")
        
        asyncio.run(run())
        
        # 정상 종료 시
        input("\n프로그램이 종료되었습니다. 엔터를 누르면 창이 닫힙니다.")
        
    except Exception as e:
        import traceback
        err_msg = traceback.format_exc()
        print(f"\n[치명적 오류 발생]\n{err_msg}")
        try:
            with open("error_log.txt", "w", encoding="utf-8") as f:
                f.write(err_msg)
            print("오류 내용이 'error_log.txt' 파일에 저장되었습니다.")
        except:
            print("로그 파일 저장 실패")
        
        input("\n오류가 발생하여 프로그램을 종료합니다. 엔터를 누르면 창이 닫힙니다.")
