"""Headless browser tests of the actual local application; no public-access claim."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright,expect

ROOT=Path(__file__).resolve().parent
ARTIFACTS=ROOT/'artifacts'
ARTIFACTS.mkdir(exist_ok=True)
BASE='http://127.0.0.1:8000'
def main():
    results=[]
    with sync_playwright() as p:
        browser=p.chromium.launch()
        context=browser.new_context(viewport={'width':1280,'height':900})
        page=context.new_page()
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(BASE)
        expect(page.locator('#value')).to_contain_text('100 JPY =')
        expect(page.locator('#fixture-T04-NORMAL-D1-A')).to_be_visible()
        # A real current upstream fetch is authorized and saved under its actual completion time.
        page.locator('#refresh').click()
        expect(page.locator('#status')).to_contain_text('fresh / none',timeout=30000)
        expect(page.locator('#refresh')).to_be_enabled(timeout=30000)
        live=context.request.get(BASE+'/api/records').json()
        current=live['current']
        assert page.locator('#value').inner_text()=='100 JPY = '+current['display_value']+' KRW'
        assert page.locator('#rows tr').count()==len(live['records'])
        assert page.locator('#plot circle').count()==len(live['records'])
        assert page.locator('#plot circle').first.get_attribute('data-value')==live['records'][0]['display_value']
        assert page.locator('#times').inner_text().startswith('출처 시각 미제공')
        assert page.locator('#source').get_attribute('href')==current['reading']['source_url']
        page.locator('#plot circle').first.focus()
        page.keyboard.press('Enter')
        expect(page.locator('#tooltip')).to_contain_text(current['display_value'])
        results.append({'check':'real fetch, schema-backed persisted table/graph/value and keyboard point','passed':True,'actual_dates':live['actual_dates'],'actual_value':current['display_value']})
        page.screenshot(path=ARTIFACTS/'actual-desktop.png',full_page=True)

        def click(key):
            page.locator('#fixture-T04-'+key).click()
            expect(page.locator('#resetReplay')).to_be_enabled()
            out=context.request.get(BASE+'/api/replay').json()
            assert out['expected_check']['passed'],out['expected_check']
            return out

        def baseline():
            page.locator('#resetReplay').click()
            expect(page.locator('#replayCount')).to_have_text('합성 기록 0건')
            a=click('NORMAL-D1-A');b=click('NORMAL-D1-B')
            assert a['current']['record_id']==b['current']['record_id']
            assert a['current']['first_fetched_at']==b['current']['first_fetched_at']
            expect(page.locator('#replayTimes')).to_contain_text('출처 시각 미제공')
            return a,b

        a,b=baseline()
        repeat=click('NORMAL-D1-B')
        assert len(repeat['records'])==1
        d2=click('NORMAL-D2')
        expect(page.locator('#replayValue')).to_have_text('120.00 pt')
        expect(page.locator('#replayCount')).to_have_text('합성 기록 2건')
        expect(page.locator('#replayChange')).to_contain_text('15.00pt 증가')
        results.append({'check':'official D1-A,D1-B,D1-B,D2 via UI; stable ID/time and 1->2 rows','passed':True})

        for key,code in [('TIMEOUT','timeout'),('AUTH-401','auth'),('RATE-429','rate_limit'),('OFFLINE','offline'),('SCHEMA-BREAK','schema_error')]:
            _,prior=baseline();out=click(key)
            assert out['records']==prior['records']
            expect(page.locator('#replayValue')).to_have_text('105.00 pt')
            expect(page.locator('#replayStatus')).to_have_text('stale / '+code)
            expect(page.locator('#replayNotice')).to_contain_text('오래된 값 · 마지막 정상 조회값')
            expect(page.locator('#retryReplay')).to_be_enabled()
            if code=='rate_limit':expect(page.locator('#replayNotice')).to_contain_text('60초')
            results.append({'check':'official UI failure '+code+' preserves value/rows/normal time','passed':True})

        page.locator('#startTimeoutTrial').click()
        expect(page.locator('#replayStatus')).to_have_text('stale / timeout')
        expect(page.locator('#retryReplay')).to_be_enabled()
        page.locator('#retryReplay').click()
        expect(page.locator('#replayStatus')).to_have_text('fresh / none')
        expect(page.locator('#replayCount')).to_have_text('합성 기록 2건')
        recovered=context.request.get(BASE+'/api/replay').json()
        assert recovered['current']['reading']['normalized_value']==120
        again=click('RECOVER-D2')
        assert len(again['records'])==2
        assert again['current']['record_id']==recovered['current']['record_id']
        assert context.request.get(BASE+'/api/records').json()==live
        assert errors==[],errors
        results.append({'check':'UI retry recovers once; repeated recovery no duplicate; live unchanged after all replay/reset','passed':True})

        # A second clean browser context has its own synthetic session and shares server live data.
        second=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
        phone=second.new_page();phone.goto(BASE)
        expect(phone.locator('#value')).to_have_text('100 JPY = '+current['display_value']+' KRW')
        expect(phone.locator('#replayCount')).to_have_text('합성 기록 0건')
        assert second.request.get(BASE+'/api/records').json()==live
        assert phone.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
        point_box=phone.locator('#plot circle').first.bounding_box()
        assert 0 <= point_box['x'] and point_box['x']+point_box['width'] <= 390
        phone.locator('#refresh').focus()
        assert phone.locator('#refresh').evaluate('(e)=>e===document.activeElement')
        phone.screenshot(path=ARTIFACTS/'actual-mobile.png',full_page=True)
        results.append({'check':'clean context reads existing live DB; replay isolated; mobile fits viewport; keyboard focus','passed':True})
        second.close();context.close();browser.close()

    (ARTIFACTS/'browser-results.json').write_text(json.dumps({'public_https_access_tested':False,'local_browser_checks':results},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'browser_checks':len(results),'passed':all(r['passed'] for r in results),'actual_dates':live['actual_dates']},ensure_ascii=False))


if __name__=="__main__":main()
