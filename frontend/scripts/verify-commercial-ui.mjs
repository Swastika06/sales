import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { chromium } from 'playwright';
import AxeBuilder from '@axe-core/playwright';
const browser=await chromium.launch({channel:'msedge',headless:true});
const context=await browser.newContext({viewport:{width:1440,height:1000}});
const page=await context.newPage(),errors=[],writes=[],accessibility=[];
page.on('pageerror',e=>errors.push(e.message));
await context.addInitScript(()=>localStorage.setItem('partner_portal_token','isolated-ui-test'));
const orgs=[{id:'tcg',legal_name:'TCG Digital',is_internal:true},{id:'customer',legal_name:'Northstar Manufacturing'},{id:'partner-org',legal_name:'Acme Consulting'}];
const capabilities=[{id:'ref',code:'REFERRAL',name:'Referral'}];
const partner={id:'partner',company_name:'Acme Consulting',capabilities,organization_id:'partner-org',status:'ACTIVE'};
const deal={id:'deal',reference:'DEAL-001',name:'Enterprise analytics',partner_id:'partner',engagement_model:'REFERRAL',commercial_version:1,migration_review_required:false,approval_status:'APPROVED',stage:'PROPOSAL',estimated_value:'100000',customer:{id:'customer',name:'Northstar Manufacturing'},responsible_user_id:'admin',stage_history:[]};
const participants=orgs.map((o,i)=>({id:'p'+i,organization_id:o.id,capability:i===2?'REFERRAL':null,access_level:i===2?'PROGRESS':'NONE',active:true}));
const component={id:'component',name:'mcube analytics',product_id:'mcube',sku_id:null,external_service:null,owner_organization_id:'tcg',seller_organization_id:'tcg',delivery_organization_id:'tcg',billing_organization_id:'customer',amount:'100000'};
const structure={opportunity_id:'deal',engagement_model:'REFERRAL',commercial_version:1,migration_review_required:false,participants,roles:['CUSTOMER_RELATIONSHIP_OWNER','BIDDER','CONTRACTING_SELLER','MCUBE_SELLER','DELIVERY_LEAD'].map(role=>({participant_id:'p0',role,scope:'OPPORTUNITY',is_primary:true})),components:[component],contracts:[],vendor_links:[]};
const result={customer_value:'100000',tcg_entitlement:'100000',partner_entitlement:'8000',vendor_cost:'10000',commission_expense:'8000',reseller_gross_margin:null,warnings:[]};
let partnerView=false;
await page.route('**/api/v1/**',async route=>{
 const req=route.request(),path=new URL(req.url()).pathname.replace('/api/v1','');
 if(req.method()!=='GET'){writes.push({path,body:req.postDataJSON()});return route.fulfill({json:path.endsWith('/preview')?{result}:structure});}
 let json=[];
 if(path==='/auth/me')json={id:'admin',email:'admin@example.com',full_name:'Nishit Saha',roles:partnerView?['PARTNER_ADMIN']:['TCG_ADMIN'],is_superuser:!partnerView,is_active:true,permissions:['sales.manage'],partner_id:partnerView?'partner':null};
 else if(path==='/deals')json=[deal];
 else if(path==='/products')json=[{id:'mcube',name:'mcube',owner_organization_id:'tcg',skus:[]}];
 else if(path==='/partners')json={items:[partner],total:1,page:1,page_size:100};
 else if(path==='/commercial/organizations')json=orgs;
 else if(path==='/commercial/opportunities/deal')json=structure;
 else if(path==='/commercial/agreements')json={partners:[],vendors:[],vendor_profiles:[]};
 else if(path==='/commercial/terms')json=[{id:'default',scope:'DEFAULT',status:'APPROVED',version:1,engagement_model:'REFERRAL',effective_from:'2026-09-28',parameters:{referral_rate:'10'}}];
 else if(path.endsWith('/snapshots'))json=[{id:'snapshot',revision:1,...(partnerView?{own_entitlement:'8000'}:{payload:{result,request:{parameters:{}}}})}];
 else if(path==='/commercial/commissions')json=[{id:'commission',opportunity_id:'deal',amount:'8000',rate:'10',eligible_amount:'80000',net_accrued:'8000',paid:'0',outstanding:'8000',status:'ACCRUED',version:0,settlement_policy:'Pay after conversion; credit agreed refunds.'}];
 else if(path==='/commercial/migration-review')json=[deal];
 return route.fulfill({json});
});
const output='node_modules/.cache/commercial-checks';await mkdir(output,{recursive:true});
try {
 await page.goto('http://localhost:5173/commercial-model?deal=deal');
 await page.getByRole('heading',{name:'Participants & responsibilities'}).waitFor();
 await page.getByRole('button',{name:'Save commercial structure'}).click();
 await page.getByRole('status').filter({hasText:'Saved.'}).waitFor();
 assert.equal(writes[0].body.expected_version,1);assert.equal(writes[0].body.roles[0].organization_id,'tcg');
 await page.screenshot({path:output+'/structure-desktop.png',fullPage:true});
 for(const tab of ['Structure','Terms','Agreements','Snapshots','Commissions','Migration review']){
  await page.getByRole('button',{name:tab,exact:true}).click();
  if(tab==='Snapshots'){await page.getByRole('button',{name:'Calculate preview'}).click();await page.getByText('FORECAST · TCG entitlement').waitFor();}
  const scan=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
  accessibility.push({tab,violations:scan.violations.map(v=>({id:v.id,impact:v.impact,targets:v.nodes.map(n=>n.target)}))});
  for(const width of [1440,768,390]){await page.setViewportSize({width,height:1000});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`${tab} overflow at ${width}`);}
  await page.setViewportSize({width:1440,height:1000});
 }
 await page.getByRole('button',{name:'Terms',exact:true}).click();
 await page.getByLabel('Eligible components').selectOption('component');
 await page.getByLabel('Eligible amount (USD)',{exact:true}).fill('80000');
 for(const name of ['Discounts','Taxes','Vendor charges','Credits','Refunds'])await page.getByLabel(name+' treatment').fill('Explicit agreed treatment');
 await page.getByLabel('Referral rate %').fill('0');
 await Promise.all([page.waitForResponse(r=>r.url().endsWith('/commercial/terms')&&r.request().method()==='POST'),page.getByRole('button',{name:'Save draft terms'}).click()]);
 const term=writes.find(w=>w.path==='/commercial/terms');assert.equal(term.body.parameters.referral_rate,'0');assert.deepEqual(term.body.parameters.eligibility.component_ids,['component']);
 await page.getByRole('button',{name:'Snapshots',exact:true}).click();await page.screenshot({path:output+'/snapshots-desktop.png',fullPage:true});
 partnerView=true;await page.reload();await page.getByRole('heading',{name:'My commercial benefit'}).waitFor();
 assert.equal(await page.getByRole('button',{name:'Terms',exact:true}).count(),0);
 await page.getByRole('button',{name:'Snapshots',exact:true}).click();await page.getByText('Your forecast entitlement:').waitFor();
 assert.equal(await page.getByText('TCG entitlement',{exact:false}).count(),0);
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:output+'/partner-mobile.png',fullPage:true});
 await writeFile(output+'/results.json',JSON.stringify({errors,accessibility,writes},null,2));
 assert.deepEqual(errors,[]);assert.equal(accessibility.reduce((n,a)=>n+a.violations.length,0),0,'Accessibility failures: see results.json');
 console.log('Commercial UI passed: structure, explicit zero terms, previews, six tabs, partner views, responsiveness and accessibility (mock API).');
}finally{await browser.close();}
