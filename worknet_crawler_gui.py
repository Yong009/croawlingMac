import sys
import os
import glob
import asyncio
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import re
import pandas as pd
from playwright.async_api import async_playwright
import traceback

# ========================================================
# 1. 브라우저 경로 찾기 및 환경 설정 (다중 OS 지원)
# ========================================================
import platform

def get_playwright_path():
    """OS별 Playwright 브라우저 저장 경로 반환"""
    system = platform.system()
    if system == 'Windows':
        return os.path.join(os.getenv("LOCALAPPDATA"), "ms-playwright")
    elif system == 'Darwin': # macOS
        return os.path.join(os.path.expanduser("~"), "Library", "Caches", "ms-playwright")
    else: # Linux etc
        return os.path.join(os.path.expanduser("~"), ".cache", "ms-playwright")

MS_PLAYWRIGHT_PATH = get_playwright_path()
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = MS_PLAYWRIGHT_PATH

def find_chromium_executable(log_func=print):
    try:
        log_func("[초기화] 브라우저 경로 검색 중...")
        if not os.path.exists(MS_PLAYWRIGHT_PATH):
            return None
        
        search_pattern = os.path.join(MS_PLAYWRIGHT_PATH, "chromium-*")
        dirs = glob.glob(search_pattern)
        
        system = platform.system()
        
        for d in sorted(dirs, reverse=True):
            if system == 'Windows':
                exe_path = os.path.join(d, "chrome-win", "chrome.exe")
            elif system == 'Darwin':
                # macOS 경로: chrome-mac/Chromium.app/Contents/MacOS/Chromium
                exe_path = os.path.join(d, "chrome-mac", "Chromium.app", "Contents", "MacOS", "Chromium")
            else:
                # Linux일 경우 (참고용)
                exe_path = os.path.join(d, "chrome-linux", "chrome")

            if os.path.exists(exe_path):
                log_func(f"  - 브라우저 발견: {exe_path}")
                return exe_path
        
        return None
    except:
        return None

def clean_text(text):
    if not isinstance(text, str):
        return str(text)
    text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F]', '', text)
    if len(text) > 32000:
        text = text[:32000] + "..."
    return text

# ========================================================
# 2. 크롤링 핵심 로직 (GUI 연동용으로 수정)
# ========================================================
class CrawlerLogic:
    def __init__(self, log_callback, progress_callback=None):
        self.log = log_callback
        self.progress = progress_callback
        self.stop_requested = False

    async def get_total_count(self):
        """전체 공고 개수만 빠르게 가져오는 함수"""
        # exec_path = find_chromium_executable(self.log) # 제거: 시스템 크롬 사용
        
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(
                    channel="chrome", # Google Chrome 사용
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled"]
                )
                page = await browser.new_page()
                url = "https://www.work24.go.kr/wk/a/b/1200/retriveDtlEmpSrchList.do"
                await page.goto(url, wait_until="domcontentloaded")
                
                # <span class="txt_total">117,217</span>
                el = page.locator("span.txt_total")
                if await el.count() > 0:
                    text = await el.inner_text() # "117,217"
                    text = text.replace(",", "").strip()
                    return int(text)
                else:
                    return 0
            except Exception as e:
                self.log(f"[오류] 개수 확인 실패 (구글 크롬이 설치되어 있어야 합니다): {e}")
                return None
            finally:
                try: await browser.close()
                except: pass

    async def run_crawl(self, target_count):
        """메인 크롤링 실행"""
        self.log(f"=== 수집 시작 (목표: {target_count}건) ===")
        self.log(f"> 시스템에 설치된 'Google Chrome'을 사용하여 실행합니다.")
        
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(
                    channel="chrome", # Google Chrome 사용
                    headless=False,
                    args=["--disable-blink-features=AutomationControlled"]
                )
            except Exception as e:
                self.log(f"[치명적 오류] 구글 크롬(Chrome)을 실행할 수 없습니다.\n컴퓨터에 크롬이 설치되어 있는지 확인해주세요.\n{e}")
                return
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...",
                viewport={'width': 1600, 'height': 900}
            )
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            await context.route("**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,eot}", lambda route: route.abort())

            page = await context.new_page()
            url = "https://www.work24.go.kr/wk/a/b/1200/retriveDtlEmpSrchList.do"
            try:
                await page.goto(url, wait_until="networkidle")
            except:
                await page.goto(url)

            jobs = []
            page_num = 1
            scheduled_count = 0
            
            sem = asyncio.Semaphore(10) # 탭 10개 제한
            tasks = []

            # 상세 수집 함수
            async def extract_detail(dtl_page, job_basic):
                async with sem:
                    try:
                        await dtl_page.wait_for_load_state("domcontentloaded")
                        await asyncio.sleep(0.3)

                        # 기업정보 탭 클릭 시도
                        try:
                            corp_tab = dtl_page.locator("a:has-text('기업정보'), button:has-text('기업정보')").first
                            if await corp_tab.count() > 0 and await corp_tab.is_visible():
                                await corp_tab.click()
                                await asyncio.sleep(0.5)
                        except: pass

                        industry = "정보 없음"
                        employees = "정보 없음"
                        fax = "정보 없음"
                        address = "정보 없음"

                        frames = [dtl_page] + dtl_page.frames
                        
                        for frame in frames:
                            try:
                                # 1. 업종
                                if industry == "정보 없음":
                                    th = frame.locator("th").filter(has_text=re.compile(r"업\s*종"))
                                    if await th.count() > 0:
                                        td = th.first.locator("xpath=following-sibling::td")
                                        if await td.count() > 0:
                                            industry = (await td.first.inner_text()).strip()
                                    
                                    if industry == "정보 없음":
                                        em = frame.locator("li em.tit").filter(has_text=re.compile(r"업\s*종"))
                                        if await em.count() > 0:
                                            li = em.first.locator("xpath=..")
                                            full = await li.inner_text()
                                            industry = full.replace(await em.first.inner_text(), "").strip()

                                # 2. 인원수
                                if employees == "정보 없음":
                                    th = frame.locator("th").filter(has_text=re.compile(r"(근로자수|사원수|직원수)"))
                                    if await th.count() > 0:
                                        td = th.first.locator("xpath=following-sibling::td")
                                        if await td.count() > 0:
                                            employees = (await td.first.inner_text()).strip()
                                    
                                    if employees == "정보 없음":
                                        em = frame.locator("li em.tit").filter(has_text=re.compile(r"(근로자수|사원수|직원수)"))
                                        if await em.count() > 0:
                                            li = em.first.locator("xpath=..")
                                            full = await li.inner_text()
                                            employees = full.replace(await em.first.inner_text(), "").strip()

                                # 3. 팩스
                                if fax == "정보 없음":
                                    th = frame.locator("th").filter(has_text=re.compile(r"(팩스|FAX|Fax)"))
                                    if await th.count() > 0:
                                        td = th.first.locator("xpath=following-sibling::td")
                                        if await td.count() > 0:
                                            fax = (await td.first.inner_text()).strip()

                                # 4. 주소
                                if address == "정보 없음":
                                    try:
                                        map_attr_el = frame.locator("[data-addr]").first
                                        if await map_attr_el.count() > 0:
                                            val = await map_attr_el.get_attribute("data-addr")
                                            if val and len(val.strip()) > 5:
                                                address = val.strip()
                                    except: pass

                                    if address == "정보 없음":
                                        th = frame.locator("th").filter(has_text=re.compile(r"(주소|소재지|위치)"))
                                        if await th.count() > 0:
                                            td = th.first.locator("xpath=following-sibling::td")
                                            if await td.count() > 0:
                                                address = (await td.first.inner_text()).strip()
                                    
                                    if address == "정보 없음":
                                        em = frame.locator("li em.tit").filter(has_text=re.compile(r"(주소|소재지|위치)"))
                                        if await em.count() > 0:
                                            li = em.first.locator("xpath=..")
                                            full = await li.inner_text()
                                            address = full.replace(await em.first.inner_text(), "").strip()
                                    
                                    # 텍스트 검색
                                    if address == "정보 없음":
                                        regions = ["서울", "경기", "인천", "부산", "대구", "광주", "대전", "울산", "세종", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"]
                                        invalid_keywords = ["연봉", "급여", "월급", "일급", "시급", "채용", "모집", "근무", "우대", "경력", "만원", "찾아줘"]
                                        for region in regions:
                                            xpath_query = f"//p[starts-with(normalize-space(.), '{region}')] | //div[starts-with(normalize-space(.), '{region}')] | //span[starts-with(normalize-space(.), '{region}')]"
                                            addr_el = frame.locator(xpath_query).first
                                            if await addr_el.count() > 0:
                                                cand_addr = re.sub(r'\s+', ' ', await addr_el.inner_text()).strip()
                                                if any(k in cand_addr for k in invalid_keywords): continue
                                                if 5 < len(cand_addr) < 80:
                                                    address = cand_addr
                                                    break
                            except: continue
                        
                        # Regex 보완 (for fax and address if still missing)
                        if fax == "정보 없음" or not fax:
                             try:
                                all_text = ""
                                for f in frames:
                                    try: all_text += await f.content()
                                    except: pass
                                pattern = re.compile(r'(?:팩스|FAX|Fax|F\s*A\s*X)(?:<[^>]*>|[\s:.-])*(\d{2,4}[-. ]\d{3,4}[-. ]\d{4})')
                                match = pattern.search(all_text)
                                if match:
                                    found_num = match.group(1).replace(" ", "").replace(".", "-")
                                    if not found_num.startswith("010"): fax = found_num
                             except: pass

                        if address == "정보 없음":
                             try:
                                all_plain = ""
                                for f in frames:
                                    try: all_plain += await f.inner_text() + "\n"
                                    except: pass
                                addr_pattern = re.compile(r'((?:서울|경기|인천|부산|대구|광주|대전|울산|세종|강원|충북|충남|전북|전남|경북|경남|제주)[가-힣\s\d,.-]+(?:로|길|동|가|읍|면|리)\s*[\d-]+(?:[,]\s*[가-힣\d\s,.-]+)?)')
                                match = addr_pattern.search(all_plain)
                                if match:
                                    found_addr = re.sub(r'\s+', ' ', match.group(0).strip())
                                    invalid_keywords = ["연봉", "급여", "월급", "일급", "시급", "채용", "모집", "근무", "우대", "경력", "만원", "찾아줘"]
                                    if not any(k in found_addr for k in invalid_keywords):
                                        if len(found_addr) < 80: address = found_addr
                             except: pass

                        job_basic.update({
                            "industry": industry,
                            "employees": employees,
                            "fax": fax,
                            "address": address
                        })
                        jobs.append(job_basic)
                        
                        if self.progress:
                             self.progress(len(jobs), target_count)
                             
                        self.log(f"[수집] {len(jobs)}번째: {job_basic['title'][:10]}... ({address})")

                    except Exception as e:
                        pass
                    finally:
                        try: await dtl_page.close()
                        except: pass

            # 메인 루프
            while scheduled_count < target_count and not self.stop_requested:
                self.log(f"--- {page_num} 페이지 탐색 중 ---")
                
                try:
                    await page.wait_for_selector('tr[id^="list"]', timeout=5000)
                except:
                    self.log("리스트를 찾을 수 없어 종료합니다.")
                    break

                rows = page.locator('tr[id^="list"]')
                count = await rows.count()
                
                if count == 0: break

                for i in range(count):
                    if scheduled_count >= target_count or self.stop_requested: break
                    
                    try:
                        row = rows.nth(i)
                        
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
                        
                        # 탭 열기
                        detail_page = None
                        try:
                            async with context.expect_page(timeout=5000) as new_page_info:
                                await title_el.click(modifiers=["Control"])
                            detail_page = await new_page_info.value
                        except: continue
                        
                        # 태스크 추가
                        task = asyncio.create_task(extract_detail(detail_page, job_basic))
                        tasks.append(task)
                        scheduled_count += 1
                        
                        await asyncio.sleep(0.5)

                    except Exception as e:
                        continue
                
                if scheduled_count >= target_count: break
                
                # 다음 페이지
                next_btn = page.locator('.btn_page.next')
                if await next_btn.count() > 0:
                    await next_btn.click()
                    await asyncio.sleep(2)
                    page_num += 1
                else:
                    self.log("다음 페이지가 없습니다.")
                    break

            # 마무리 대기
            self.log("진행 중인 태스크 마무리 중...")
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            
            # 저장
            self.save_to_excel(jobs)
            await browser.close()
            self.log("=== 모든 작업 완료 ===")

    def save_to_excel(self, jobs):
        try:
            df = pd.DataFrame(jobs)
            
            # 컬럼명 한글로 변경 (CLI 버전과 동일하게)
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
            
            df = df.applymap(clean_text)
            filename = 'worknet_results_gui.xlsx'
            df.to_excel(filename, index=False, engine='openpyxl')
            self.log(f"[저장 완료] 파일명: {filename} ({len(jobs)}건)")
            messagebox.showinfo("완료", f"수집이 완료되었습니다.\n총 {len(jobs)}건")
        except Exception as e:
            self.log(f"[저장 실패] {e}")
            messagebox.showerror("오류", f"저장 중 오류가 발생했습니다.\n{e}")

# ========================================================
# 3. GUI 메인 클래스
# ========================================================
class WorknetGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Worknet Crawler Pro")
        self.root.geometry("600x500")
        
        self.crawler = CrawlerLogic(self.append_log, self.update_progress)
        self.loop = asyncio.new_event_loop()
        
        self.setup_ui()
        
        # 별도 스레드에서 이벤트 루프 실행 및 초기 데이터 로드
        self.thread = threading.Thread(target=self.start_async_loop, daemon=True)
        self.thread.start()
        
        # 시작하자마자 총 개수 조회 태스크 예약
        self.run_async(self.load_total_count())

    def start_async_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run_async(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def append_log(self, msg):
        # Thread-safe GUI update
        self.root.after(0, lambda: self._update_log(msg))

    def _update_log(self, msg):
        self.log_area.insert(tk.END, msg + "\n")
        self.log_area.see(tk.END)

    def update_progress(self, current, total):
        self.root.after(0, lambda: self.lbl_progress.config(text=f"현재 진행: {current} / {total} 건 수집됨"))

    def reset_ui_state(self):
        self.btn_start.config(state="normal", text="수집 시작")
        self.entry_count.config(state="normal")

    def setup_ui(self):
        # 스타일링
        style = ttk.Style()
        style.configure("TLabel", font=("Malgun Gothic", 10))
        style.configure("TButton", font=("Malgun Gothic", 10, "bold"))
        
        # 상단 프레임 (정보 표시)
        top_frame = ttk.LabelFrame(self.root, text="채용공고 현황", padding=10)
        top_frame.pack(fill="x", padx=10, pady=5)
        
        self.lbl_total = ttk.Label(top_frame, text="총 채용공고 수 조회 중...", foreground="blue")
        self.lbl_total.pack(side="left")

        self.lbl_progress = ttk.Label(top_frame, text="대기 중...", foreground="red")
        self.lbl_progress.pack(side="right")
        
        # 중간 프레임 (입력 및 실행)
        mid_frame = ttk.LabelFrame(self.root, text="수집 설정", padding=10)
        mid_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Label(mid_frame, text="수집할 개수:").pack(side="left", padx=5)
        
        self.entry_count = ttk.Entry(mid_frame, width=10)
        self.entry_count.insert(0, "100")
        self.entry_count.pack(side="left", padx=5)
        
        self.btn_start = ttk.Button(mid_frame, text="수집 시작", command=self.on_start_click)
        self.btn_start.pack(side="right", padx=5)

        # 로그 프레임
        log_frame = ttk.LabelFrame(self.root, text="진행 상황 로그", padding=10)
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.log_area = scrolledtext.ScrolledText(log_frame, height=15, state='normal')
        self.log_area.pack(fill="both", expand=True)

    async def load_total_count(self):
        self.append_log(">>> 전체 공고 수를 조회하고 있습니다...")
        total = await self.crawler.get_total_count()
        if total is not None:
            text = f"현재 등록된 총 채용공고: {total:,} 건"
            self.root.after(0, lambda: self.lbl_total.config(text=text, foreground="green"))
            self.append_log(f">>> 조회 완료: {total:,} 건")
        else:
            self.root.after(0, lambda: self.lbl_total.config(text="조회 실패 (로그 확인)", foreground="red"))

    def on_start_click(self):
        try:
            count = int(self.entry_count.get())
        except ValueError:
            messagebox.showerror("입력 오류", "숫자만 입력해주세요.")
            return
            
        self.btn_start.config(state="disabled", text="실행 중...")
        self.entry_count.config(state="disabled")
        
        # 크롤링 시작
        future = self.run_async(self.crawler.run_crawl(count))
        future.add_done_callback(lambda f: self.root.after(0, self.reset_ui_state))

if __name__ == "__main__":
    root = tk.Tk()
    app = WorknetGUI(root)
    root.mainloop()
