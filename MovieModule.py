from multiprocessing import Queue

from playwright.async_api import  async_playwright
import asyncio


class MovieModule:
    def __init__(self,browser,context,page):
        self.browser = browser
        self.context = context
        self.page = page
        self.frame=None
    @classmethod
    async def create(cls,board_q:Queue):
        p=await async_playwright().start()
        browser = await p.chromium.launch(headless=False, args=["--start-maximized"])
        context = await browser.new_context(no_viewport=True, accept_downloads=False)
        page = await context.new_page()
        await page.goto("https://www3.fsonline.app/", wait_until="domcontentloaded", timeout=0)
        self= cls(browser,context,page)


        asyncio.create_task(self.closeAds())
        return self
    async def isModuleActive(self):
        try:
            f = await self.page.title()
            print(f)
            return True
        except Exception:
            return False
    async def closeAds(self):
        selectors = [
            "button:has-text('x')",
            "button:has-text('X')",
            "button:has-text('Close')",
            "[aria-label*='close' i]",
            "[role='button']:has-text('Close')",

        ]
        while True:
            for context in self.browser.contexts:
                for page in context.pages[:]:
                    if page.url.startswith("https://www3.fsonline.app/"):
                        for sel in selectors:
                            locator = page.locator(sel)
                            if await locator.count() > 0:
                                await locator.first.click()
                    else:
                        await page.close()
            await asyncio.sleep(1)
    async def loadMovie(self,movieName):
        """
        Loads the specified movie
        """
        ...

        search = self.page.get_by_role('textbox')
        await search.wait_for()
        await search.fill(movieName)
        await self.page.keyboard.press("Enter")
        await self.page.locator('.see').click()
        await self.page.locator("#show_player_ajax").click()

        frameLocator = self.page.locator("iframe").first
        await frameLocator.wait_for()
        self.frame=frameLocator.content_frame
        videoStatus=False
        while not videoStatus:
            videoStatus = await self.frame.locator(':root').evaluate("""() => {
                            const video = document.querySelector('video')
                            if(video){
                                const videoPlayer=jwplayer();
                                videoPlayer.play();
                                videoPlayer.setCurrentCaptions(1);
                                videoPlayer.setFullscreen(true);
                                return true;
                            }
                            return false;   
                        }""")
            await asyncio.sleep(0.5)
    async def playMovie(self):
        await  self.frame.locator(':root').evaluate("""() => {
            const video = document.querySelector('video');
            if(video){
                const videoPlayer=jwplayer();
                videoPlayer.play();
            }
        }""")
    async def pauseMovie(self):
        await self.frame.locator(':root').evaluate("""() => {
            const video = document.querySelector('video');
            if(video){
                const videoPlayer=jwplayer();
                videoPlayer.pause();
            }
        }""")