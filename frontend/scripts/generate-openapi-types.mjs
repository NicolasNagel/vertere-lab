import { readFile, writeFile } from 'node:fs/promises'

const document = JSON.parse(await readFile(new URL('../openapi.json', import.meta.url), 'utf8'))
const schemas = document.components?.schemas ?? {}

function typeName(ref) {
  return ref.split('/').at(-1)
}

function render(schema) {
  if (!schema) return 'unknown'
  if (schema.$ref) return typeName(schema.$ref)
  if (schema.enum) return schema.enum.map((value) => JSON.stringify(value)).join(' | ')
  if (schema.anyOf) return schema.anyOf.map(render).join(' | ')
  if (schema.allOf) return schema.allOf.map(render).join(' & ')
  if (schema.type === 'array') return `Array<${render(schema.items)}>`
  if (schema.type === 'object' || schema.properties) {
    if (!schema.properties) return 'Record<string, unknown>'
    const required = new Set(schema.required ?? [])
    const fields = Object.entries(schema.properties).map(
      ([name, value]) => `  ${JSON.stringify(name)}${required.has(name) ? '' : '?'}: ${render(value)}`,
    )
    return `{\n${fields.join('\n')}\n}`
  }
  if (schema.type === 'integer' || schema.type === 'number') return 'number'
  if (schema.type === 'boolean') return 'boolean'
  if (schema.type === 'null') return 'null'
  if (schema.type === 'string') return 'string'
  return 'unknown'
}

const lines = [
  '/* eslint-disable */',
  '// Generated from backend OpenAPI. Run `npm run api:generate`; do not edit.',
  '',
]
for (const [name, schema] of Object.entries(schemas).sort(([left], [right]) => left.localeCompare(right))) {
  lines.push(`export type ${name} = ${render(schema)}`, '')
}

await writeFile(
  new URL('../src/shared/api/generated.ts', import.meta.url),
  `${lines.join('\n').trimEnd()}\n`,
)
