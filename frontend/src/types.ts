export type FieldKind =
  | 'int'
  | 'float'
  | 'bool'
  | 'enum'
  | 'gradient'
  | 'swatch'
  | 'seed'

export interface VisibleIf {
  key: string
  value: unknown
}

export interface Field {
  key: string
  label: string
  kind: FieldKind
  default: unknown
  group: 'shape' | 'color' | 'advanced'
  min?: number
  max?: number
  step?: number
  choices?: string[]
  unit?: string
  help?: string
  visibleIf?: VisibleIf
}

export interface TypeDependentSpec {
  default: number
  min: number
  max: number
  fixed?: boolean
  label?: string
}

export interface TemplateSchema {
  name: string
  label: string
  blurb: string
  colorParadigm: string
  fields: Field[]
  typeDependent?: Record<string, Record<string, Record<string, TypeDependentSpec>>>
}

export interface TemplateSummary {
  name: string
  label: string
  blurb: string
  colorParadigm: string
}

export type GradientStop = [number, [number, number, number]]

export type ParamValue = number | boolean | string | GradientStop[] | [number, number, number]

export type Params = Record<string, ParamValue>

export interface Look {
  id: string
  label: string
  template: string
  templateLabel: string
  series: string
  blurb: string
  thumb: string | null
  params: Params
}
