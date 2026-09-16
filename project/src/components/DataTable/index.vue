<template>
  <view class="data-table">
    <!-- 表头 -->
    <view class="data-table__header">
      <view
        v-for="col in columns"
        :key="col.key"
        class="data-table__th"
        :style="{ width: col.width, textAlign: col.align || 'center' }"
      >
        <text class="data-table__th-text">{{ col.title }}</text>
      </view>
    </view>

    <!-- 表体 -->
    <view v-if="data.length > 0" class="data-table__body">
      <view
        v-for="(row, idx) in data"
        :key="idx"
        class="data-table__tr"
        :class="{ 'data-table__tr--striped': striped && idx % 2 === 1 }"
      >
        <view
          v-for="col in columns"
          :key="col.key"
          class="data-table__td"
          :style="{ width: col.width, textAlign: col.align || 'center' }"
        >
          <text
            class="data-table__td-text"
            :class="{ 'data-table__td-text--num': isNumeric(row[col.key]) }"
          >{{ row[col.key] }}</text>
        </view>
      </view>
    </view>

    <!-- 空态 -->
    <view v-else class="data-table__empty">
      <text class="data-table__empty-text">{{ emptyText }}</text>
    </view>
  </view>
</template>

<script setup lang="ts">
/**
 * DataTable - 数据/资费展示组件
 * @description 横向滚动数据表格（类目资费校验页等数据展示场景）：列配置化、斑马纹、
 *              数值单元格等宽数字（tabular-nums）、空数据统一展示。
 *
 * @example
 * <DataTable :columns="columns" :data="rows" />
 */
interface DataTableColumn {
  /** 数据字段 key */
  key: string
  /** 列标题 */
  title: string
  /** 列宽（CSS 宽度，如 15%） */
  width?: string
  /** 对齐方式，默认 center */
  align?: 'left' | 'center' | 'right'
}

interface Props {
  /** 列配置 */
  columns: DataTableColumn[]
  /** 行数据（Record<string, any>[]） */
  data: Record<string, any>[]
  /** 是否启用斑马纹（默认 true） */
  striped?: boolean
  /** 空数据文案（默认「暂无数据」） */
  emptyText?: string
}

withDefaults(defineProps<Props>(), {
  striped: true,
  emptyText: '暂无数据',
})

/** 数值判断：可转数字且非空（用于等宽数字样式） */
function isNumeric(value: unknown): boolean {
  if (value === null || value === undefined || value === '') return false
  return typeof value === 'number' || (!isNaN(Number(value)))
}
</script>

<style lang="scss" scoped>
@import '@/styles/tokens/_index.scss';

.data-table {
  width: 100%;
  background-color: $u-white;
  border: 1rpx solid $u-border-color;
  border-radius: $up-radius-md;
  overflow: hidden;

  &__header {
    display: flex;
    background-color: $u-bg-color;
    border-bottom: 1rpx solid $u-border-color;
  }

  &__th {
    flex-shrink: 0;
    padding: $up-space-3 $up-space-2;

    &-text {
      font-size: $up-font-size-caption;
      font-weight: $up-font-weight-bold;
      color: $u-main-color;
    }
  }

  &__body {
    max-height: 70vh;
    overflow-y: auto;
  }

  &__tr {
    display: flex;
    border-bottom: 1rpx solid $u-border-color;

    &:last-child {
      border-bottom: none;
    }

    &--striped {
      background-color: $u-bg-color;
    }
  }

  &__td {
    flex-shrink: 0;
    padding: $up-space-3 $up-space-2;

    &-text {
      font-size: $up-font-size-caption;
      color: $u-content-color;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;

      /* 数值等宽数字：费率/金额对齐不跳动 */
      &--num {
        font-variant-numeric: tabular-nums;
        color: $u-main-color;
        font-weight: $up-font-weight-medium;
      }
    }
  }

  &__empty {
    padding: $up-space-8 0;
    text-align: center;

    &-text {
      font-size: $up-font-size-caption;
      color: $u-tips-color;
    }
  }
}
</style>
