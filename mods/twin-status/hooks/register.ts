import type { EngineInterface, Register } from 'claude-code'

// Shows "twin: DISCOVER · 12 screens · 4 tasks · 0 open gaps" in the status line
// and refreshes it whenever a file under docs/ or state/ changes.

type Engine = Pick<EngineInterface, 'fs' | 'ui'>

const TRACKED = /^(docs|state)\//

async function countMd($: Engine, dir: string): Promise<number> {
  try {
    const entries = await $.fs.list(dir)
    return entries.filter(f => f.kind === 'file' && f.name.endsWith('.md')).length
  } catch {
    return 0
  }
}

async function refresh($: Engine): Promise<void> {
  let mode = 'not started'
  try {
    const parsed = JSON.parse(await $.fs.read('state/mode.json')) as { mode?: string }
    if (parsed.mode) mode = parsed.mode
  } catch {
    // no state yet
  }
  const screens = await countMd($, 'docs/raw/screens')
  const tasks = await countMd($, 'docs/raw/tasks')
  let gaps = 0
  try {
    const text = await $.fs.read('docs/verify/gaps.md')
    gaps = text.split('\n').filter(line => line.includes('**Status:** open')).length
  } catch {
    // no gaps file yet
  }
  $.ui.status(`twin: ${mode} · ${screens} screens · ${tasks} tasks · ${gaps} open gaps`)
}

function touchesTracked(path: string | undefined): boolean {
  return path !== undefined && TRACKED.test(path.replace(/\\/g, '/'))
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await refresh($)
    return next(e)
  })

  on('tool.call', { tool: 'Write' }, async ($, e, next) => {
    const result = await next(e)
    if (touchesTracked(e.file_path)) await refresh($)
    return result
  })

  on('tool.call', { tool: 'Edit' }, async ($, e, next) => {
    const result = await next(e)
    if (touchesTracked(e.file_path)) await refresh($)
    return result
  })

  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    const result = await next(e)
    if (/state\/|docs\//.test(e.command)) await refresh($)
    return result
  })
}
