export type ApiState = {connected:boolean; status?:string; audit?:{valid:boolean;count:number}; sandbox?:string; error?:string};
const base = import.meta.env.VITE_API_BASE ?? '';
export async function getStatus():Promise<ApiState>{
  try { const response=await fetch(`${base}/api/status`,{headers:{Accept:'application/json'}}); if(!response.ok) throw new Error(`HTTP ${response.status}`); return {connected:true,...await response.json()}; }
  catch(error){return {connected:false,error:error instanceof Error?error.message:'Connection failed'};}
}
export async function getAgents(){const r=await fetch(`${base}/api/agents`);if(!r.ok)throw new Error(`HTTP ${r.status}`);return r.json();}
