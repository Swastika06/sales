import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { randomUUID } from "node:crypto";
import { PGlite } from "@electric-sql/pglite";
const buffer = await readFile(process.argv[2] || "../.venv/commercial-upgrade.sql");
const sql = buffer.toString(buffer[0] === 255 ? "utf16le" : "utf8").replace(/^\uFEFF/, "").replace("CREATE EXTENSION IF NOT EXISTS vector;", "-- Unrelated pgvector extension excluded in isolated migration test.");
const index = sql.indexOf("-- Running upgrade 20260923_0004 -> 20260930_0005");
assert(index > 0);
const db = new PGlite();
async function insert(table, fields) {
 const values = { id: randomUUID(), ...fields };
 const columns = Object.keys(values);
 await db.query(`INSERT INTO ${table} (${columns.join(',')}) VALUES (${columns.map((_, i) => '$' + (i + 1)).join(',')})`, Object.values(values));
 return values.id;
}
try {
 await db.exec(sql.slice(0,index));
 const user = await insert('users', {email:'admin@example.com',full_name:'Admin',hashed_password:'unused'});
 const type = await insert('partner_types',{code:'RESELLER',name:'Reseller'});
 const tier = await insert('partner_tiers',{code:'GOLD',name:'Gold',rank:2});
 const partner = await insert('partners',{company_name:'Legacy partner',company_email:'p@example.com',primary_contact_name:'Contact',primary_contact_email:'c@example.com',status:'ACTIVE',partner_type_id:type,tier_id:tier});
 const product = await insert('products',{code:'MCUBE',name:'mcube'});
 const customer = await insert('customers',{name:'Customer',country_code:'IN',created_by_id:user});
 const deal = await insert('opportunities',{reference:'LEGACY-CLASSIFIED',partner_id:partner,product_id:product,customer_id:customer,name:'Project',estimated_value:'100000',created_by_id:user});
 await insert('opportunities',{reference:'LEGACY-AMBIGUOUS',partner_id:partner,product_id:product,customer_id:customer,name:'Project',estimated_value:'100000',created_by_id:user});
 const quote = await insert('quotes',{reference:'LEGACY-QUOTE',opportunity_id:deal,partner_id:partner,status:'ACCEPTED',commercial_model:'RESELLER',subtotal:'100000',discount_total:'24000',total:'76000',created_by_id:user});
 const snapshot = JSON.stringify({total:'76000.00',tier_discount:'5'});
 await insert('quote_revisions',{quote_id:quote,revision_number:1,snapshot,created_by_id:user});
 await insert('orders',{reference:'LEGACY-ORDER',status:'CONFIRMED',quote_id:quote,partner_id:partner,billing_name:'Customer',billing_address:'Billing address',billing_email:'b@example.com',total:'76000',quote_snapshot:snapshot,created_by_id:user});
 await insert('documents',{title:'Tier price sheet',category:'PRICING',visibility:'PARTNER_TIER',partner_tier_id:tier,created_by_id:user});
 await insert('tier_pricing_adjustments',{tier_id:tier,discount_percentage:'5',effective_from:'2020-01-01'});
 await db.exec(sql.slice(index));
 const one = async text => (await db.query(text)).rows[0];
 assert.equal((await one('SELECT total FROM quotes')).total,'76000.00');
 assert.equal((await one('SELECT quote_snapshot FROM orders')).quote_snapshot.tier_discount,'5');
 assert.equal((await one('SELECT snapshot FROM quote_revisions')).snapshot.total,'76000.00');
 assert.equal((await one('SELECT visibility FROM documents')).visibility,'TCG_INTERNAL');
 assert.equal((await one('SELECT is_active FROM tier_pricing_adjustments')).is_active,false);
 assert.equal((await one('SELECT count(*)::int AS n FROM partner_capabilities')).n,1);
 assert.equal((await one("SELECT engagement_model FROM opportunities WHERE reference='LEGACY-CLASSIFIED'")).engagement_model,'RESELLER');
 assert.equal((await one("SELECT engagement_model FROM opportunities WHERE reference='LEGACY-AMBIGUOUS'")).engagement_model,null);
 assert.equal((await one('SELECT count(*)::int AS n FROM opportunities WHERE migration_review_required')).n,2);
 assert.equal((await one('SELECT parameters FROM commercial_term_versions')).parameters.referral_rate,'10');
 await assert.rejects(db.exec("UPDATE quote_revisions SET snapshot='{}'"),/immutable/);
 await assert.rejects(db.exec("UPDATE commercial_term_versions SET parameters='{}'"),/new version/);
 await insert('opportunities',{reference:'NEW-DIRECT',partner_id:null,product_id:product,customer_id:customer,name:'Direct project',estimated_value:'100000',created_by_id:user,engagement_model:'DIRECT',migration_review_required:false});
 assert.equal((await one("SELECT partner_id FROM opportunities WHERE reference='NEW-DIRECT'")).partner_id,null);
 console.log('Legacy PostgreSQL migration passed: history preserved, capabilities mapped, ambiguity queued, document grants restricted, Direct supported, immutable history protected.');
} catch (error) { console.error(error.message); process.exitCode=1; } finally { await db.close(); }
const fresh = new PGlite();
try { await fresh.exec(sql); console.log('Fresh PostgreSQL installation: all five migrations passed (unrelated pgvector extension excluded).'); } catch(error) { console.error(error.message); process.exitCode=1; } finally { await fresh.close(); }
