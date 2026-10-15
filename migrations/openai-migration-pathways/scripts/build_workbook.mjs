// Maintainer-only authoring: requires @oai/artifact-tool. Evaluator stays stdlib Python.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import crypto from 'node:crypto';
import {Workbook,SpreadsheetFile} from '@oai/artifact-tool';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const r=JSON.parse(await fs.readFile(path.join(root,'data/capabilities.json'),'utf8'));
const workbook=Workbook.create();
const previews=process.env.MIGRATION_PREVIEW_DIRECTORY;
const rowsBySheet={};
function grid(name,title,note,headers,rows,widths){
 const s=workbook.worksheets.add(name);s.showGridLines=false;
 s.getRangeByIndexes(0,0,rows.length+6,headers.length).format.font={name:'Arial',size:10,color:'#17324D'};
 s.getRange('A2').values=[[title]];s.getRange('A2').format.font={name:'Arial',size:15,bold:true,color:'#17324D'};
 s.getRange('A4').values=[[note]];s.getRange('A4').format.font={italic:true,color:'#52677C'};
 s.getRangeByIndexes(5,0,1,headers.length).values=[headers];
 s.getRangeByIndexes(5,0,1,headers.length).format={fill:'#244E73',font:{name:'Arial',size:10,bold:true,color:'#FFFFFF'},wrapText:true,rowHeight:32};
 if(rows.length)s.getRangeByIndexes(6,0,rows.length,headers.length).values=rows;
 s.getRangeByIndexes(6,0,Math.max(rows.length,1),headers.length).format={rowHeight:34,verticalAlignment:'center',wrapText:true};
 widths.forEach((w,i)=>s.getRangeByIndexes(0,i,rows.length+6,1).format.columnWidthPx=w);
 if(rows.length>20)s.freezePanes.freezeRows(6);
 rowsBySheet[name]={headers,rows};return s;
}
const overview=grid('Overview','OpenAI migration targets',`Version ${r.registry_version}. Evidence reviewed ${r.snapshot_date}. GPT-OSS and Daybreak excluded.`,
 ['Model','AWS context tokens','AWS max output','Route definitions'],
 r.models.map(m=>[m.name,m.limits.context_tokens,m.limits.max_output_tokens,null]),[230,170,170,150]);
overview.getRange('B7:C15').setNumberFormat('#,##0');
const routeRows=r.routes.map((x,i)=>['R'+String(i+1).padStart(3,'0'),x.model_name,x.endpoint,x.api,x.inference_mode,x.partition,x.model_id,x.entry_regions.join(', '),x.cache.implicit.status,x.cache.explicit.status,x.features.structured_outputs.status,x.features.inline_guardrails.status]);
grid('Routes','Exact Bedrock routes','Read capability notes and evaluate the required combination before selecting a route.',
 ['Route key','Model','Endpoint','API','Routing','Partition','Model/profile ID','Entry Regions','Implicit cache','Explicit cache','Schema','Inline safety'],routeRows,[85,170,155,160,135,120,290,650,110,110,110,110]);
for(let i=0;i<r.models.length;i++)overview.getRange(`D${i+7}`).formulas=[[`=COUNTIFS('Routes'!$B$7:$B$${r.routes.length+6},A${i+7})`]];
overview.getRange('A18').values=[['Interpretation']];overview.getRange('A18').format.font={bold:true};
const legend=[['YES','Documented for the stated route; account and runtime checks remain.'],['NO','Native feature is incompatible with this route.'],['VERIFY','Evidence or an exact contract remains unresolved.'],['ORCHESTRATED','Separate application orchestration is required.']];
overview.getRange('A20:B23').values=legend;overview.getRange('B20:D23').merge(true); // One explanatory cell per row.
for(let i=0;i<legend.length;i++)overview.getRange(`B${20+i}`).values=[[legend[i][1]]];
overview.getRange('A20:D23').format={rowHeight:32,wrapText:true};
overview.getRange('A25').values=[['Use the Python evaluator for combinations, dates, limits and preferences.']];
overview.getRange('A27').values=[['Pricing rows retain their source scope; missing rates are not zero.']];
const featureRows=[];
r.routes.forEach((x,i)=>Object.entries(x.features).forEach(([f,c])=>featureRows.push(['R'+String(i+1).padStart(3,'0'),f,c.status,c.reason,c.sources.join(', ')])));
const features=grid('Features','Capabilities by route','Route keys link to the Routes sheet. These are individual claims, not combined request approvals.',
 ['Route key','Feature','State','Explanation','Evidence IDs'],featureRows,[85,210,135,660,290]);
const statuses=features.getRange(`C7:C${featureRows.length+6}`);
statuses.conditionalFormats.add('containsText',{text:'VERIFY',format:{fill:'#FFF2CD',font:{color:'#765600'}}});
statuses.conditionalFormats.add('containsText',{text:'NO',format:{fill:'#FBE3DF',font:{color:'#982F26'}}});
statuses.conditionalFormats.add('containsText',{text:'ORCHESTRATED',format:{fill:'#DDEBF7',font:{color:'#244E73'}}});
const ruleRows=r.rules.map(x=>['All routes',x.required_features.join(' + '),x.status,x.reason,x.sources.join(', ')]);
r.routes.forEach((x,i)=>{const key='R'+String(i+1).padStart(3,'0');
 x.interactions.forEach(c=>ruleRows.push([key,c.required_features.join(' + '),c.status,c.reason,c.sources.join(', ')]));
 Object.entries(x.region_constraints).forEach(([region,c])=>ruleRows.push([key,'Entry Region '+region,c.status,c.reason,c.sources.join(', ')]));
});
grid('Rules','Combination and Region qualifications','These rules qualify the individual feature states. Apply the evaluator to the complete requirements.',
 ['Route key','Required combination / scope','State','Explanation','Evidence IDs'],ruleRows,[100,340,120,650,240]);
const priceRows=r.models.flatMap(m=>m.pricing.map(p=>[m.name,p.section,p.inference_option,p.input,p.cache_write,p.cache_read,p.output,p.sources.join(', ')]));
const pricing=grid('Pricing','Documented Bedrock token rates','USD per 1 million tokens. Match tier, routing, partition and context band. Blank means not supplied.',
 ['Model','Tier / context / partition','Inference option','Input','Cache write','Cache read','Output','Evidence IDs'],priceRows,[175,420,360,105,105,105,105,135]);
pricing.getRange(`D7:G${priceRows.length+6}`).setNumberFormat('$0.00##');pricing.getRange(`A7:H${priceRows.length+6}`).format.rowHeight=48;
const evidenceRows=r.sources.map(s=>[s.id,s.publisher,s.scope,new Date(s.checked_at),s.url]);
const evidence=grid('Evidence','Official documentation snapshots','Snapshots and SHA-256 hashes are packaged with the registry. Direct OpenAI claims are scoped separately.',
 ['Evidence ID','Publisher','Scope','Retrieved (UTC)','Official URL'],evidenceRows,[215,95,140,125,800]);
evidence.getRange(`D7:D${evidenceRows.length+6}`).setNumberFormat('yyyy-mm-dd');
workbook.recalculate();
console.log((await workbook.inspect({kind:'table',range:'Overview!A6:D15',include:'values,formulas',tableMaxRows:10,tableMaxCols:4,maxChars:1800})).ndjson);
const errors=await workbook.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#SPILL!',options:{useRegex:true,maxResults:10},summary:'Formula error check'});
console.log(errors.ndjson);
if(previews){await fs.mkdir(previews,{recursive:true});for(const [name,range] of [['Overview','A1:D27'],['Routes','A1:F12'],['Features','A1:D14'],['Pricing','A1:G12'],['Evidence','A1:E10'],['Rules','A1:D13']]){
 if(process.env.MIGRATION_PREVIEW_SHEETS && !process.env.MIGRATION_PREVIEW_SHEETS.split(',').includes(name))continue;
 const img=await workbook.render({sheetName:name,range,scale:1});await fs.writeFile(path.join(previews,name+'.png'),new Uint8Array(await img.arrayBuffer()));}}
const xlsx=await SpreadsheetFile.exportXlsx(workbook);await xlsx.save(path.join(root,'assets/workbooks/openai-bedrock-feature-availability-matrix.xlsx'));
console.log(JSON.stringify({sheets:Object.keys(rowsBySheet),routes:r.routes.length,capabilityRows:featureRows.length,pricingRows:priceRows.length}));
