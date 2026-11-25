from pathlib import Path
import os, re, base64, threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parent
# Offline mode exercises real Chromium DOM, CSS and JS. Only navigation/storage are substituted.
class Quiet(SimpleHTTPRequestHandler):
 def log_message(self,*a): pass

def run(project):
 folder=ROOT/project
 # Also works from a project's own tests folder when copied into a ZIP.
 if not folder.exists(): folder=Path(__file__).resolve().parents[1]
 offline=os.getenv('OFFLINE_TEST','0')=='1'
 server=None
 if not offline:
  server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(folder)))
  threading.Thread(target=server.serve_forever,daemon=True).start()
 with sync_playwright() as p:
  executable=os.getenv('CHROMIUM_PATH'); browser=p.chromium.launch(executable_path=executable,args=['--no-sandbox'] if executable else [])
  page=browser.new_page(viewport={'width':1440,'height':900}); errors=[]; page.on('pageerror',lambda e:errors.append(str(e)))
  def load():
   nonlocal page
   if not offline:
    page.goto(f'http://127.0.0.1:{server.server_port}/'); return
   saved=page.evaluate('window.__testStorage || {}'); viewport=page.viewport_size; page.close(); page=browser.new_page(viewport=viewport); page.on('pageerror',lambda e:errors.append(str(e)))
   html=(folder/'index.html').read_text(); html=re.sub(r'<script[^>]*src="[^"]+"[^>]*></script>','',html);html=html.replace('<link rel="stylesheet" href="style.css">','<style>'+(folder/'style.css').read_text()+'</style>')
   page.set_content(html)
   page.evaluate('saved=>{window.__testStorage=saved;Object.defineProperty(window,"localStorage",{configurable:true,value:{getItem(k){return Object.hasOwn(saved,k)?saved[k]:null},setItem(k,v){saved[k]=String(v)},removeItem(k){delete saved[k]}}})}',saved)
   if project=='studio-frontend':
    for f in ['react.min.js','react-dom.min.js']: page.add_script_tag(content=(folder/'vendor'/f).read_text())
   js=(folder/'script.js').read_text()
   if project=='studio-frontend':
    assets={f.stem:'data:image/svg+xml;base64,'+base64.b64encode(f.read_bytes()).decode() for f in (folder/'assets').glob('*.svg')}
    # Replace image URL resolution only to let the restricted browser render local assets.
    import json
    js=js.replace("'assets/'+p.image+'.svg'", '('+json.dumps(assets)+')[p.image]')
   page.add_script_tag(content=js)
  def shot(name): page.wait_for_timeout(400); page.screenshot(path=str(folder/'docs'/name),full_page=True,animations='disabled')
  load()
  if project=='multi-step-form':
   expect(page.locator('#progress')).to_have_attribute('aria-valuenow','25');shot('desktop-preview.png')
   page.locator('#next').click();expect(page.locator('[name=fullName]')).to_have_attribute('aria-invalid','true')
   for n,v in {'fullName':'Alex Morgan','email':'bad','city':'Abbottabad'}.items():page.locator(f'[name={n}]').fill(v)
   page.locator('#next').click();expect(page.locator('[name=email]')).to_have_attribute('aria-invalid','true');page.locator('[name=email]').fill('alex@example.com');page.locator('#next').click();expect(page.locator('#percent')).to_have_text('50%')
   page.locator('[name=institution]').fill('Demo University');load();expect(page.locator('[name=institution]')).to_have_value('Demo University');expect(page.locator('#percent')).to_have_text('50%')
   page.locator('[name=qualification]').select_option("Bachelor's degree");page.locator('[name=field]').fill('Computer Science');page.locator('[name=year]').fill('1900');page.locator('#next').click();expect(page.locator('[name=year]')).to_have_attribute('aria-invalid','true');page.locator('[name=year]').fill('2027');page.locator('#next').click();expect(page.locator('#percent')).to_have_text('75%')
   page.locator('[name=interest]').select_option('Frontend development');page.locator('[name=work]').select_option('Remote');page.locator('[name=goals]').fill('<b>Build accessible apps</b>');page.locator('#prev').click();expect(page.locator('#percent')).to_have_text('50%');page.locator('#next').click();page.locator('#next').click();expect(page.locator('#summary')).to_contain_text('Alex Morgan');expect(page.locator('#summary')).to_contain_text('<b>Build accessible apps</b>');expect(page.locator('#summary b')).to_have_count(0);expect(page.locator('#percent')).to_have_text('100%');page.locator('#next').click();expect(page.locator('[name=consent]')).to_have_attribute('aria-invalid','true');shot('review-preview.png');page.get_by_role('button',name='Edit Personal details').click();expect(page.locator('#percent')).to_have_text('25%');page.locator('#next').click();page.locator('#next').click();page.locator('#next').click();page.locator('[name=consent]').check();page.locator('#next').click();expect(page.locator('#success')).to_be_visible();load();expect(page.locator('[name=fullName]')).to_have_value('');expect(page.locator('#percent')).to_have_text('25%')
  elif project=='chat-interface':
   expect(page.locator('.message.received')).to_have_count(1);expect(page.locator('#send')).to_be_disabled();page.locator('#message').fill('   ');expect(page.locator('#send')).to_be_disabled();page.locator('#message').fill('Hello!');page.locator('#send').click();expect(page.locator('.message.sent')).to_have_count(1);expect(page.locator('.message.received')).to_have_count(2);expect(page.locator('.message time')).to_have_count(3)
   page.locator('#message').fill('What is localStorage?');page.locator('#message').press('Enter');expect(page.locator('.message.sent')).to_have_count(2);load();expect(page.locator('.message.sent')).to_have_count(2);expect(page.locator('.message.received')).to_have_count(3);expect(page.locator('.message.received').last).to_contain_text('localStorage');shot('desktop-preview.png');page.set_viewport_size({'width':390,'height':844});shot('mobile-preview.png');page.set_viewport_size({'width':1440,'height':900})
   page.locator('#message').fill('<img src=x onerror=alert(1)>');page.locator('#send').click();expect(page.locator('.message.sent').last).to_contain_text('<img');expect(page.locator('.bubble img')).to_have_count(0);expect(page.locator('.message.received')).to_have_count(4);page.locator('#message').fill('Thank you!');page.locator('#send').click();expect(page.locator('.message.received')).to_have_count(5);page.once('dialog',lambda d:d.accept());page.locator('#clear').click();expect(page.locator('.message.sent')).to_have_count(0);load();expect(page.locator('.message.received')).to_have_count(1)
  else:
   expect(page.locator('.slide-caption strong')).to_have_text('Forma Objects');expect(page.locator('.project')).to_have_count(3);shot('desktop-preview.png');page.get_by_role('button',name='Next slide').click();expect(page.locator('.slide-caption strong')).to_have_text('Fieldwork');page.get_by_role('button',name='Previous slide').click();expect(page.locator('.slide-caption strong')).to_have_text('Forma Objects');page.get_by_role('button',name='Previous slide').click();expect(page.locator('.slide-caption strong')).to_have_text('Orbit Motion');page.get_by_role('button',name='Load more projects').click();expect(page.locator('.project')).to_have_count(6);page.get_by_role('button',name='Digital',exact=True).click();expect(page.locator('.project')).to_have_count(2);page.get_by_role('button',name='All',exact=True).click();expect(page.locator('.project')).to_have_count(3)
   page.get_by_role('button',name='Submit demo inquiry').click();expect(page.locator('#contact-error-name')).to_have_text('Enter your name.');page.locator('#contact-name').fill('Alex Morgan');page.locator('#contact-email').fill('bad');page.locator('#contact-service').select_option('Web & digital');page.locator('#contact-message').fill('A responsive website for a demo project.');page.get_by_role('button',name='Submit demo inquiry').click();expect(page.locator('#contact-error-email')).to_have_text('Enter a valid email address.');page.locator('#contact-email').fill('alex@example.com');page.get_by_role('button',name='Submit demo inquiry').click();expect(page.locator('.result')).to_contain_text('Form validated successfully');page.set_viewport_size({'width':390,'height':844});page.locator('#menu-toggle').click();expect(page.locator('#nav-links')).to_be_visible();page.keyboard.press('Escape');expect(page.locator('#nav-links')).not_to_be_visible();page.locator('#menu-toggle').click();page.locator('#nav-links a').first.click();expect(page.locator('#menu-toggle')).to_have_attribute('aria-expanded','false');load();page.evaluate('window.scrollTo({top:0,behavior:"instant"})');shot('mobile-preview.png')
  if project=='multi-step-form':page.set_viewport_size({'width':390,'height':844});shot('mobile-preview.png')
  for w in [320,390,768,1024,1440]:
   page.set_viewport_size({'width':w,'height':900});page.wait_for_timeout(50);assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(project,w,page.evaluate('document.documentElement.scrollWidth'))
  assert not errors,errors; browser.close();print(project,'PASS', 'offline harness' if offline else 'localhost')
 if server:server.shutdown()
if __name__=='__main__':
 import sys
 run(sys.argv[1] if len(sys.argv)>1 else Path(__file__).resolve().parents[1].name)
