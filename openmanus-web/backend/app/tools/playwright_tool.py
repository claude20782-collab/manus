"""
Playwright Browser Automation Tool
Handles browser launching, navigation, screenshots, and element interaction
"""

import asyncio
import base64
import logging
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, Page, Browser, BrowserContext

logger = logging.getLogger(__name__)


class PlaywrightTool:
    """
    Playwright-based browser automation tool
    Supports headless operation with screenshot streaming
    """
    
    def __init__(
        self,
        session_id: str,
        session_dir: str,
        headless: bool = True,
        viewport_width: int = 1280,
        viewport_height: int = 720
    ):
        self.session_id = session_id
        self.session_dir = session_dir
        self.headless = headless
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        
        # Playwright objects
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        # Current screenshot (bytes)
        self.current_screenshot: Optional[bytes] = None
        
        # Last action coordinates for overlay
        self.last_action_coords: Optional[Dict[str, int]] = None
        self.last_action_type: Optional[str] = None
    
    async def initialize(self):
        """Initialize Playwright and launch browser"""
        try:
            self.playwright = await async_playwright().start()
            
            # Launch browser with remote debugging enabled
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-gpu',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--remote-debugging-port=9222',
                    '--remote-debugging-address=0.0.0.0'
                ]
            )
            
            # Create context with viewport
            self.context = await self.browser.new_context(
                viewport={
                    'width': self.viewport_width,
                    'height': self.viewport_height
                },
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            # Create page
            self.page = await self.context.new_page()
            
            # Take initial screenshot
            await self._capture_screenshot()
            
            logger.info("Playwright browser initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Playwright: {e}")
            return False
    
    async def _capture_screenshot(self):
        """Capture current page screenshot"""
        if self.page:
            try:
                self.current_screenshot = await self.page.screenshot(
                    type='jpeg',
                    quality=80,
                    full_page=False
                )
            except Exception as e:
                logger.error(f"Screenshot capture failed: {e}")
    
    async def close(self):
        """Close browser and cleanup resources"""
        try:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("Playwright browser closed")
        except Exception as e:
            logger.error(f"Error closing browser: {e}")
    
    async def navigate(self, url: str) -> Dict[str, Any]:
        """Navigate to a URL"""
        if not self.page:
            await self.initialize()
        
        try:
            # Ensure URL has protocol
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            response = await self.page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Capture screenshot after navigation
            await self._capture_screenshot()
            
            self.last_action_type = "navigate"
            self.last_action_coords = None
            
            return {
                "success": True,
                "url": self.page.url,
                "title": await self.page.title(),
                "status": response.status if response else None
            }
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def click(self, selector: str) -> Dict[str, Any]:
        """Click on an element matching the selector"""
        if not self.page:
            return {"success": False, "error": "Browser not initialized"}
        
        try:
            # Wait for element to be visible
            element = await self.page.wait_for_selector(selector, state='visible', timeout=10000)
            
            # Get element position for overlay
            box = await element.bounding_box()
            if box:
                self.last_action_coords = {
                    'x': int(box['x'] + box['width'] / 2),
                    'y': int(box['y'] + box['height'] / 2),
                    'width': int(box['width']),
                    'height': int(box['height'])
                }
                self.last_action_type = "click"
            
            # Click the element
            await element.click()
            
            # Small delay for any resulting navigation/animation
            await asyncio.sleep(0.5)
            
            # Capture screenshot
            await self._capture_screenshot()
            
            return {
                "success": True,
                "selector": selector,
                "position": self.last_action_coords
            }
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def type_text(self, selector: str, text: str) -> Dict[str, Any]:
        """Type text into an input field"""
        if not self.page:
            return {"success": False, "error": "Browser not initialized"}
        
        try:
            # Wait for element
            element = await self.page.wait_for_selector(selector, state='visible', timeout=10000)
            
            # Get element position for overlay
            box = await element.bounding_box()
            if box:
                self.last_action_coords = {
                    'x': int(box['x']),
                    'y': int(box['y']),
                    'width': int(box['width']),
                    'height': int(box['height'])
                }
                self.last_action_type = "type"
            
            # Clear and type
            await element.fill('')
            await element.type(text, delay=50)  # Simulate human typing
            
            # Capture screenshot
            await self._capture_screenshot()
            
            return {
                "success": True,
                "selector": selector,
                "text": text
            }
        except Exception as e:
            logger.error(f"Type failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def scroll(self, direction: str) -> Dict[str, Any]:
        """Scroll up or down"""
        if not self.page:
            return {"success": False, "error": "Browser not initialized"}
        
        try:
            if direction.lower() == 'down':
                await self.page.evaluate('window.scrollBy(0, window.innerHeight * 0.8)')
            elif direction.lower() == 'up':
                await self.page.evaluate('window.scrollBy(0, -window.innerHeight * 0.8)')
            else:
                return {"success": False, "error": f"Invalid direction: {direction}"}
            
            # Small delay
            await asyncio.sleep(0.3)
            
            # Capture screenshot
            await self._capture_screenshot()
            
            self.last_action_type = "scroll"
            self.last_action_coords = None
            
            return {
                "success": True,
                "direction": direction
            }
        except Exception as e:
            logger.error(f"Scroll failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def extract_data(self, format: str = 'json') -> Dict[str, Any]:
        """Extract structured data from the current page"""
        if not self.page:
            return {"success": False, "error": "Browser not initialized"}
        
        try:
            if format.lower() == 'json':
                # Extract structured data using accessibility tree
                data = await self.page.evaluate('''() => {
                    return {
                        title: document.title,
                        url: window.location.href,
                        meta: Array.from(document.querySelectorAll('meta')).map(m => ({
                            name: m.getAttribute('name') || m.getAttribute('property'),
                            content: m.getAttribute('content')
                        })),
                        headings: Array.from(document.querySelectorAll('h1, h2, h3')).map(h => ({
                            tag: h.tagName,
                            text: h.textContent.trim()
                        })),
                        links: Array.from(document.querySelectorAll('a[href]')).slice(0, 50).map(a => ({
                            text: a.textContent.trim().substring(0, 100),
                            href: a.href
                        })),
                        tables: Array.from(document.querySelectorAll('table')).map(t => {
                            const rows = Array.from(t.querySelectorAll('tr'));
                            return rows.map(row => 
                                Array.from(row.querySelectorAll('td, th')).map(cell => cell.textContent.trim())
                            );
                        })
                    };
                }''')
                
            elif format.lower() == 'html':
                # Extract simplified HTML
                data = await self.page.evaluate('''() => {
                    return document.body.innerHTML.substring(0, 50000);
                }''')
                
            else:
                return {"success": False, "error": f"Unsupported format: {format}"}
            
            # Capture screenshot
            await self._capture_screenshot()
            
            return {
                "success": True,
                "format": format,
                "data": data
            }
        except Exception as e:
            logger.error(f"Data extraction failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_page_content(self) -> str:
        """Get the current page HTML content"""
        if not self.page:
            return ""
        return await self.page.content()
    
    async def get_accessibility_snapshot(self) -> Dict[str, Any]:
        """Get accessibility snapshot for LLM analysis"""
        if not self.page:
            return {}
        
        try:
            snapshot = await self.page.accessibility.snapshot()
            return snapshot or {}
        except Exception as e:
            logger.error(f"Accessibility snapshot failed: {e}")
            return {}
    
    async def get_current_state(self) -> Dict[str, Any]:
        """Get comprehensive current browser state for agent decision making"""
        if not self.page:
            return {"error": "Browser not initialized"}
        
        try:
            # Get basic info
            url = self.page.url
            title = await self.page.title()
            
            # Get interactive elements
            elements = await self.page.evaluate('''() => {
                const interactives = [];
                
                // Buttons
                document.querySelectorAll('button, [role="button"]').forEach(el => {
                    if (el.offsetParent !== null) {
                        const rect = el.getBoundingClientRect();
                        interactives.push({
                            type: 'button',
                            text: el.textContent.trim().substring(0, 50),
                            x: Math.round(rect.x + rect.width / 2),
                            y: Math.round(rect.y + rect.height / 2),
                            selector: el.id ? `#${el.id}` : el.className ? `.${el.className.split(' ')[0]}` : ''
                        });
                    }
                });
                
                // Links
                document.querySelectorAll('a[href]').forEach(el => {
                    if (el.offsetParent !== null) {
                        const rect = el.getBoundingClientRect();
                        interactives.push({
                            type: 'link',
                            text: el.textContent.trim().substring(0, 50),
                            href: el.href,
                            x: Math.round(rect.x + rect.width / 2),
                            y: Math.round(rect.y + rect.height / 2)
                        });
                    }
                });
                
                // Inputs
                document.querySelectorAll('input, textarea').forEach(el => {
                    if (el.offsetParent !== null) {
                        const rect = el.getBoundingClientRect();
                        interactives.push({
                            type: 'input',
                            placeholder: el.placeholder,
                            value: el.value,
                            x: Math.round(rect.x),
                            y: Math.round(rect.y)
                        });
                    }
                });
                
                return interactives.slice(0, 100);
            }''')
            
            return {
                "url": url,
                "title": title,
                "interactive_elements": elements,
                "screenshot_available": self.current_screenshot is not None
            }
        except Exception as e:
            logger.error(f"Failed to get page state: {e}")
            return {"error": str(e)}
