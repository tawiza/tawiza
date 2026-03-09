'use client';

import * as React from 'react';
import {
  ColumnDef,
  ColumnFiltersState,
  SortingState,
  VisibilityState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from '@tanstack/react-table';
import { ArrowUpDown, ChevronDown, Search } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { GlassCard } from '@/components/ui/glass-card';
import { Badge } from '@/components/ui/badge';
import { Department, REGIONS, formatEnterprises } from '@/data/departments';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';

// Size categories based on enterprise count
const SIZE_CATEGORIES = {
  small: { label: 'Petit', max: 30000 },
  medium: { label: 'Moyen', min: 30000, max: 80000 },
  large: { label: 'Grand', min: 80000 },
} as const;

// Dynamism categories based on growth rate
const DYNAMISM_CATEGORIES = {
  high: { label: 'Forte croissance', min: 2.0, color: 'bg-success' },
  moderate: { label: 'Croissance moderee', min: 0, max: 2.0, color: 'bg-warning' },
  decline: { label: 'Declin', max: 0, color: 'bg-error' },
} as const;

// DOM-TOM codes
const DOM_TOM_CODES = ['971', '972', '973', '974', '976'];

function getDynamismCategory(growth: number): keyof typeof DYNAMISM_CATEGORIES {
  if (growth >= 2.0) return 'high';
  if (growth >= 0) return 'moderate';
  return 'decline';
}

function getSizeCategory(enterprises: number): keyof typeof SIZE_CATEGORIES {
  if (enterprises < 30000) return 'small';
  if (enterprises < 80000) return 'medium';
  return 'large';
}

interface DataTableDepartmentsProps {
  data: Department[];
}

export function DataTableDepartments({ data }: DataTableDepartmentsProps) {
  const router = useRouter();
  const [sorting, setSorting] = React.useState<SortingState>([]);
  const [columnFilters, setColumnFilters] = React.useState<ColumnFiltersState>([]);
  const [columnVisibility, setColumnVisibility] = React.useState<VisibilityState>({});
  const [globalFilter, setGlobalFilter] = React.useState('');
  const [regionFilter, setRegionFilter] = React.useState<string>('all');
  const [growthFilter, setGrowthFilter] = React.useState<string>('all');
  const [sizeFilter, setSizeFilter] = React.useState<string>('all');
  const [dynamismFilter, setDynamismFilter] = React.useState<string>('all');
  const [territoryFilter, setTerritoryFilter] = React.useState<string>('all');

  // Define columns
  const columns: ColumnDef<Department>[] = [
    {
      accessorKey: 'code',
      header: ({ column }) => (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          className="hover:bg-transparent p-0"
        >
          Code
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      ),
      cell: ({ row }) => (
        <span className="font-mono font-medium text-primary">
          {row.getValue('code')}
        </span>
      ),
    },
    {
      accessorKey: 'name',
      header: ({ column }) => (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          className="hover:bg-transparent p-0"
        >
          Departement
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      ),
      cell: ({ row }) => <span className="font-medium">{row.getValue('name')}</span>,
    },
    {
      accessorKey: 'region',
      header: 'Region',
      cell: ({ row }) => (
        <span className="text-muted-foreground">{row.getValue('region')}</span>
      ),
      filterFn: (row, id, value) => {
        if (value === 'all') return true;
        return row.getValue(id) === value;
      },
    },
    {
      accessorKey: 'enterprises',
      header: ({ column }) => (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          className="hover:bg-transparent p-0"
        >
          Entreprises
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      ),
      cell: ({ row }) => (
        <span className="font-medium">
          {formatEnterprises(row.getValue('enterprises'))}
        </span>
      ),
    },
    {
      accessorKey: 'growth',
      header: ({ column }) => (
        <Button
          variant="ghost"
          onClick={() => column.toggleSorting(column.getIsSorted() === 'asc')}
          className="hover:bg-transparent p-0"
        >
          Croissance
          <ArrowUpDown className="ml-2 h-4 w-4" />
        </Button>
      ),
      cell: ({ row }) => {
        const growth = row.getValue('growth') as number;
        const isPositive = growth >= 0;
        return (
          <span
            className={cn(
              'font-medium',
              isPositive ? 'text-[var(--success)]' : 'text-[var(--error)]'
            )}
          >
            {isPositive ? '+' : ''}{growth.toFixed(1)}%
          </span>
        );
      },
      filterFn: (row, id, value) => {
        if (value === 'all') return true;
        const growth = row.getValue(id) as number;
        if (value === 'positive') return growth >= 0;
        if (value === 'negative') return growth < 0;
        return true;
      },
    },
    {
      id: 'dynamism',
      header: 'Dynamisme',
      cell: ({ row }) => {
        const growth = row.getValue('growth') as number;
        const category = getDynamismCategory(growth);
        const config = DYNAMISM_CATEGORIES[category];
        return (
          <Badge
            variant="outline"
            className={cn(
              'text-[10px] px-2 py-0.5 border-0 text-white',
              config.color
            )}
          >
            {category === 'high' ? 'Dynamique' : category === 'moderate' ? 'Stable' : 'Declin'}
          </Badge>
        );
      },
    },
  ];

  // Filter data based on all filters
  const filteredData = React.useMemo(() => {
    let result = [...data];

    // Region filter
    if (regionFilter !== 'all') {
      result = result.filter(d => d.region === regionFilter);
    }

    // Growth filter (legacy - positive/negative)
    if (growthFilter !== 'all') {
      result = result.filter(d => {
        if (growthFilter === 'positive') return d.growth >= 0;
        if (growthFilter === 'negative') return d.growth < 0;
        return true;
      });
    }

    // Size filter (enterprise count)
    if (sizeFilter !== 'all') {
      result = result.filter(d => {
        const size = getSizeCategory(d.enterprises);
        return size === sizeFilter;
      });
    }

    // Dynamism filter (growth level)
    if (dynamismFilter !== 'all') {
      result = result.filter(d => {
        const dynamism = getDynamismCategory(d.growth);
        return dynamism === dynamismFilter;
      });
    }

    // Territory filter (Metropole vs DOM-TOM)
    if (territoryFilter !== 'all') {
      result = result.filter(d => {
        const isDomTom = DOM_TOM_CODES.includes(d.code);
        if (territoryFilter === 'metropole') return !isDomTom;
        if (territoryFilter === 'domtom') return isDomTom;
        return true;
      });
    }

    return result;
  }, [data, regionFilter, growthFilter, sizeFilter, dynamismFilter, territoryFilter]);

  const table = useReactTable({
    data: filteredData,
    columns,
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    onColumnVisibilityChange: setColumnVisibility,
    globalFilterFn: (row, columnId, filterValue) => {
      const value = row.getValue(columnId);
      if (typeof value === 'string') {
        return value.toLowerCase().includes(filterValue.toLowerCase());
      }
      return false;
    },
    state: {
      sorting,
      columnFilters,
      columnVisibility,
      globalFilter,
    },
    onGlobalFilterChange: setGlobalFilter,
    initialState: {
      pagination: {
        pageSize: 10,
      },
    },
  });

  // Handle row click
  const handleRowClick = (department: Department) => {
    router.push(`/dashboard/ai-chat?department=${department.code}`);
  };

  // Count active filters
  const activeFiltersCount = [
    regionFilter !== 'all',
    growthFilter !== 'all',
    sizeFilter !== 'all',
    dynamismFilter !== 'all',
    territoryFilter !== 'all',
  ].filter(Boolean).length;

  return (
    <div className="space-y-4">
      {/* Filters - 2 rows for expert-level filtering */}
      <div className="space-y-3">
        {/* Row 1: Search + Primary filters */}
        <div className="flex flex-col gap-3 md:flex-row md:items-center">
          {/* Search */}
          <div className="relative max-w-xs flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Rechercher..."
              value={globalFilter}
              onChange={(e) => setGlobalFilter(e.target.value)}
              className="pl-9 glass"
            />
          </div>

          {/* Region filter */}
          <Select value={regionFilter} onValueChange={setRegionFilter}>
            <SelectTrigger className="w-[180px] glass">
              <SelectValue placeholder="Region" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Toutes les regions</SelectItem>
              {REGIONS.map((region) => (
                <SelectItem key={region} value={region}>
                  {region}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Territory filter (Metropole/DOM-TOM) */}
          <Select value={territoryFilter} onValueChange={setTerritoryFilter}>
            <SelectTrigger className="w-[140px] glass">
              <SelectValue placeholder="Territoire" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tous</SelectItem>
              <SelectItem value="metropole">Metropole</SelectItem>
              <SelectItem value="domtom">DOM-TOM</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Row 2: Economic filters + Reset */}
        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div className="flex flex-wrap items-center gap-3">
            {/* Size filter */}
            <Select value={sizeFilter} onValueChange={setSizeFilter}>
              <SelectTrigger className="w-[140px] glass">
                <SelectValue placeholder="Taille" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Toutes tailles</SelectItem>
                <SelectItem value="small">Petit (&lt;30K)</SelectItem>
                <SelectItem value="medium">Moyen (30-80K)</SelectItem>
                <SelectItem value="large">Grand (&gt;80K)</SelectItem>
              </SelectContent>
            </Select>

            {/* Dynamism filter */}
            <Select value={dynamismFilter} onValueChange={setDynamismFilter}>
              <SelectTrigger className="w-[160px] glass">
                <SelectValue placeholder="Dynamisme" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tous niveaux</SelectItem>
                <SelectItem value="high">Dynamique (&gt;2%)</SelectItem>
                <SelectItem value="moderate">Stable (0-2%)</SelectItem>
                <SelectItem value="decline">Declin (&lt;0%)</SelectItem>
              </SelectContent>
            </Select>

            {/* Legacy growth filter */}
            <Select value={growthFilter} onValueChange={setGrowthFilter}>
              <SelectTrigger className="w-[130px] glass">
                <SelectValue placeholder="Signe" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">+/-</SelectItem>
                <SelectItem value="positive">Positive</SelectItem>
                <SelectItem value="negative">Negative</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Reset button with filter count */}
          <Button
            variant="outline"
            onClick={() => {
              setGlobalFilter('');
              setRegionFilter('all');
              setGrowthFilter('all');
              setSizeFilter('all');
              setDynamismFilter('all');
              setTerritoryFilter('all');
            }}
            className="transition-normal hover:glow-cyan"
          >
            Reinitialiser
            {activeFiltersCount > 0 && (
              <Badge variant="secondary" className="ml-2 h-5 w-5 rounded-full p-0 text-[10px]">
                {activeFiltersCount}
              </Badge>
            )}
          </Button>
        </div>
      </div>

      {/* Table */}
      <GlassCard noPadding>
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id} className="hover:bg-transparent border-b border-border/50">
                {headerGroup.headers.map((header) => (
                  <TableHead key={header.id} className="text-foreground">
                    {header.isPlaceholder
                      ? null
                      : flexRender(header.column.columnDef.header, header.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows?.length ? (
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  onClick={() => handleRowClick(row.original)}
                  className="cursor-pointer transition-normal hover:bg-muted/50 border-b border-border/30"
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center">
                  Aucun resultat.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </GlassCard>

      {/* Pagination */}
      <div className="flex items-center justify-between px-2">
        <div className="text-sm text-muted-foreground">
          {table.getFilteredRowModel().rows.length} departement(s)
        </div>
        <div className="flex items-center gap-4">
          {/* Page size selector */}
          <Select
            value={String(table.getState().pagination.pageSize)}
            onValueChange={(value) => table.setPageSize(Number(value))}
          >
            <SelectTrigger className="w-[80px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="10">10</SelectItem>
              <SelectItem value="25">25</SelectItem>
              <SelectItem value="50">50</SelectItem>
            </SelectContent>
          </Select>

          {/* Page navigation */}
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
            >
              Precedent
            </Button>
            <span className="text-sm text-muted-foreground">
              Page {table.getState().pagination.pageIndex + 1} sur{' '}
              {table.getPageCount()}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
            >
              Suivant
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
