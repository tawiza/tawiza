// TAJINE department data - placeholder for future use
type RowObj = {
  checked?: string;
  department: string;
  code: string;
  region: string;
  enterprises: number;
  growth: string;
};

const tableDataDepartments: RowObj[] = [
  {
    checked: '',
    department: 'Paris',
    code: '75',
    region: 'Ile-de-France',
    enterprises: 524000,
    growth: '+2.3%',
  },
  {
    checked: '',
    department: 'Bouches-du-Rhone',
    code: '13',
    region: 'Provence-Alpes-Cote d\'Azur',
    enterprises: 187000,
    growth: '+1.8%',
  },
  {
    checked: '',
    department: 'Nord',
    code: '59',
    region: 'Hauts-de-France',
    enterprises: 168000,
    growth: '+1.2%',
  },
  {
    checked: '',
    department: 'Rhone',
    code: '69',
    region: 'Auvergne-Rhone-Alpes',
    enterprises: 156000,
    growth: '+2.1%',
  },
  {
    checked: '',
    department: 'Hauts-de-Seine',
    code: '92',
    region: 'Ile-de-France',
    enterprises: 142000,
    growth: '+1.9%',
  },
];

export default tableDataDepartments;
