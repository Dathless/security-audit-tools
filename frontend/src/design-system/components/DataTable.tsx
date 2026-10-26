import type { ReactElement, ReactNode } from "react";
import { useId, useMemo, useState } from "react";
import "./DataTable.css";

export interface DataColumn<T> {
  /** khoá trong row dùng để sort/search; cột render thuần (action) thì để rỗng */
  key?: string;
  label: string;
  mono?: boolean;
  sortable?: boolean;
  align?: "left" | "center" | "right";
  render?: (row: T) => ReactNode;
}

interface DataTableProps<T> {
  columns: DataColumn<T>[];
  rows: T[];
  /** 1 cột thuần render làm cột "hành động", hiển thị dưới th giống td */
  renderColumn?: (row: T) => ReactNode;
  rowKey: string;
  search?: boolean;
  searchPlaceholder?: string;
  searchText?: (row: T) => string;
  toolbar?: ReactNode;
  emptyText?: string;
  /** giới hạn chiều cao khối bảng + cuộn dọc (vd "420px") — mặc định auto */
  maxHeight?: string;
}

type SortDir = "asc" | "desc";

function toSortable(value: unknown): string | number {
  if (typeof value === "number") return value;
  if (typeof value === "boolean") return value ? 1 : 0;
  const s = value == null ? "" : String(value);
  const n = Number(s);
  return s !== "" && !Number.isNaN(n) ? n : s;
}

function asRecord(row: unknown): Record<string, unknown> {
  return row as Record<string, unknown>;
}

/**
 * Bảng dữ liệu có sort + filter bằng bàn phím. Cột kỹ thuật dùng font mono,
 * header có focus-visible, hover row.
 */
export function DataTable<T>({
  columns,
  rows,
  renderColumn,
  rowKey,
  search = true,
  searchPlaceholder = "Lọc…",
  searchText,
  toolbar,
  emptyText = "Không có dữ liệu.",
  maxHeight,
}: DataTableProps<T>): ReactElement {
  const searchId = useId();
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const filtered = useMemo(() => {
    let result = rows;
    if (search && query.trim()) {
      const q = query.trim().toLowerCase();
      result = rows.filter((row) => {
        const rec = asRecord(row);
        return searchText?.(row).toLowerCase().includes(q) || columns.some((col) => {
          if (!col.key) return false;
          const raw = rec[col.key];
          if (raw == null) return false;
          return String(raw).toLowerCase().includes(q);
        });
      });
    }
    if (sortKey) {
      const dir = sortDir === "asc" ? 1 : -1;
      result = [...result].sort((a, b) => {
        const recA = asRecord(a);
        const recB = asRecord(b);
        const va = toSortable(recA[sortKey]);
        const vb = toSortable(recB[sortKey]);
        if (typeof va === "number" && typeof vb === "number") return (va - vb) * dir;
        return String(va).localeCompare(String(vb)) * dir;
      });
    }
    return result;
  }, [rows, columns, query, sortKey, sortDir, search, searchText]);

  function onSort(key: string): void {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  function ariaSort(key: string): "ascending" | "descending" | "none" {
    if (sortKey !== key) return "none";
    return sortDir === "asc" ? "ascending" : "descending";
  }

  return (
    <div className="datatable">
      {search ? (
        <div className="datatable-toolbar">
          {toolbar}
          <label className="sr-only" htmlFor={searchId}>
            Tìm kiếm
          </label>
          <input
            id={searchId}
            className="datatable-search"
            type="search"
            value={query}
            placeholder={searchPlaceholder}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
      ) : null}

      <div className="datatable-scroll" role="region" aria-label="Bảng dữ liệu cuộn" tabIndex={0} style={maxHeight ? { maxHeight } : undefined}>
        <table className="datatable-table" data-testid="data-table">
          <thead>
            <tr>
              {columns.map((col) => {
                const thClass = [
                  col.align ? `th-${col.align}` : "",
                  col.mono ? "th-mono" : "",
                ]
                  .filter(Boolean)
                  .join(" ");
                return (
                  <th key={col.label} aria-sort={ariaSort(col.key ?? "")} className={thClass || undefined}>
                    {col.sortable && col.key ? (
                      <button
                        type="button"
                        className={`th-sort${sortKey === col.key ? ` sort-${sortDir}` : ""}`}
                        onClick={() => onSort(col.key!)}
                      >
                        {col.label}
                        <span className="th-arrow" aria-hidden="true">
                          {sortKey === col.key ? (sortDir === "asc" ? "▲" : "▼") : ""}
                        </span>
                      </button>
                    ) : (
                      col.label
                    )}
                  </th>
                );
              })}
              {renderColumn ? <th className="th-action">Hành động</th> : null}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td className="datatable-empty" colSpan={columns.length + (renderColumn ? 1 : 0)}>
                  {query.trim() ? "Không có kết quả phù hợp. Thử đổi hoặc xóa bộ lọc." : emptyText}
                </td>
              </tr>
            ) : (
              filtered.map((row) => {
                const rec = asRecord(row);
                return (
                  <tr key={String(rec[rowKey] ?? "")}>
                    {columns.map((col) => {
                      const content = col.render ? col.render(row) : String(rec[col.key ?? ""] ?? "—");
                      const tdClass = [
                        col.align ? `td-${col.align}` : "",
                        col.mono ? "td-mono" : "",
                      ]
                        .filter(Boolean)
                        .join(" ");
                      return (
                        <td key={col.label} className={tdClass || undefined}>
                          {content}
                        </td>
                      );
                    })}
                    {renderColumn ? <td className="td-action">{renderColumn(row)}</td> : null}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
