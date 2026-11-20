import {useEffect, useState, type FormEvent} from 'react';
import {createRoot} from 'react-dom/client';
import domain from './domain.json';
import './style.css';

type Value = string | number | boolean;
type RecordData = Record<string, Value>;
type Entity = (typeof domain.entities)[number];
const label = (value: string) => value.replaceAll('_', ' ').replace(/^./, letter => letter.toUpperCase());

async function api<T>(path: string, token: string, payload?: RecordData): Promise<T> {
  const headers: Record<string, string> = {'Content-Type': 'application/json'};
  if (token) headers.Authorization = 'Bearer ' + token;
  const response = await fetch('/api/' + path, {
    method: payload ? 'POST' : 'GET', headers, body: payload ? JSON.stringify(payload) : undefined,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body.detail;
    const message = Array.isArray(detail) && detail[0]?.field
      ? label(detail[0].field) + ' failed ' + detail[0].rule + ' validation'
      : typeof detail === 'string' ? detail : 'Invalid input or service unavailable';
    throw new Error(message);
  }
  return response.json();
}

function EntityScreen({entity, view, token}: {entity: Entity; view: string; token: string}) {
  const derived = new Set(domain.rules.filter(rule => rule.entity === entity.id && rule.operator === 'multiply').map(rule => rule.field));
  const fields = Object.entries(entity.fields);
  const [draft, setDraft] = useState<RecordData>({});
  const [result, setResult] = useState<RecordData>({});
  const [records, setRecords] = useState<RecordData[]>([]);
  const [message, setMessage] = useState('');
  const [pending, setPending] = useState(false);
  const [offset, setOffset] = useState(0);
  const [confirm, setConfirm] = useState(false);

  useEffect(() => {
    if (view !== 'records') return;
    let current = true;
    setPending(true);
    setMessage('');
    api<RecordData[]>(entity.id + '?limit=25&offset=' + offset, token)
      .then(rows => {if (current) setRecords(rows);})
      .catch((error: Error) => {if (current) setMessage(error.message);})
      .finally(() => {if (current) setPending(false);});
    return () => {current = false;};
  }, [entity, offset, token, view]);

  async function submit(save: boolean) {
    setConfirm(false);
    setPending(true);
    setMessage('');
    setResult({});
    try {
      const payload = Object.fromEntries(fields.filter(([name]) => !derived.has(name)).map(([name, kind]) => {
        const raw = draft[name];
        if (kind === 'integer') {
          if (raw === undefined || raw === '' || !Number.isInteger(Number(raw))) throw new Error('Enter an integer for ' + label(name));
          return [name, Number(raw)];
        }
        return [name, raw ?? (kind === 'boolean' ? false : '')];
      }));
      const data = await api<RecordData>(entity.id + (save ? '' : '/preview'), token, payload);
      setResult(data);
      setMessage(save ? 'Saved' : 'Calculated');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'Request failed');
    } finally {
      setPending(false);
    }
  }

  return <section>
    <nav aria-label="Current entity">
      <a id="entry" href={'#/' + entity.id + '/entry'}>Entry</a>
      <a id="records" href={'#/' + entity.id + '/records'}>Records</a>
    </nav>
    {view === 'records' ? <>
      <h2>Records</h2>
      <div className="scroll"><table><thead><tr>{fields.map(([name]) => <th key={name} scope="col">{label(name)}</th>)}</tr></thead>
      <tbody>{records.map((record, index) => <tr key={String(record.id)}>{fields.map(([name]) =>
        <td key={name} id={index === 0 ? 'latest_' + name : undefined}>{String(record[name] ?? '')}</td>)}</tr>)}</tbody></table></div>
      <button disabled={!offset || pending} onClick={() => setOffset(offset - 25)}>Previous</button>
      <button disabled={records.length < 25 || pending} onClick={() => setOffset(offset + 25)}>Next</button>
    </> : <form noValidate onSubmit={(event: FormEvent) => {event.preventDefault(); void submit(false);}}>
      {fields.map(([name, kind]) => <div className="field" key={name}><label htmlFor={name}>{label(name)}</label>
        {derived.has(name) ? <output id={name}>{String(result[name] ?? '')}</output> :
          kind === 'boolean' ? <input id={name} type="checkbox" checked={draft[name] === true}
            onChange={event => setDraft({...draft, [name]: event.target.checked})}/> :
          <input id={name} type={kind === 'integer' ? 'number' : 'text'} value={String(draft[name] ?? '')}
            onChange={event => setDraft({...draft, [name]: event.target.value})}/>}
      </div>)}
      <div className="actions"><button id="calculate" disabled={pending}>Calculate</button>
      <button type="button" id="save" disabled={pending} onClick={() => setConfirm(true)}>Save</button></div>
    </form>}
    {confirm && <dialog open aria-labelledby="confirm-heading"><h2 id="confirm-heading">Save this record?</h2>
      <button id="confirm_save" onClick={() => void submit(true)}>Confirm</button>
      <button onClick={() => setConfirm(false)}>Cancel</button></dialog>}
    <p id="status" role="status" aria-live="polite">{pending ? 'Loading…' : message}</p>
  </section>;
}

function App() {
  const [route, setRoute] = useState(location.hash);
  const [token, setToken] = useState('');
  useEffect(() => {
    const change = () => setRoute(location.hash);
    window.addEventListener('hashchange', change);
    return () => window.removeEventListener('hashchange', change);
  }, []);
  const [, id, view = 'entry'] = route.slice(1).split('/');
  const entity = domain.entities.find(item => item.id === id) ?? domain.entities[0];
  return <main><h1>{domain.title}</h1>
    <details><summary>API access</summary><label>Access token <input type="password" value={token} autoComplete="off"
      onChange={event => setToken(event.target.value)}/></label></details>
    {domain.entities.length > 1 && <nav aria-label="Entities">{domain.entities.map(item =>
      <a key={item.id} href={'#/' + item.id + '/entry'}>{item.title}</a>)}</nav>}
    <EntityScreen key={entity.id + '/' + view} entity={entity} view={view} token={token}/>
  </main>;
}

createRoot(document.getElementById('root')!).render(<App/>);
