<script setup lang="ts">
import type { SimpleRom } from "@/stores/roms";
import RAvatarRom from "@/components/common/Game/RAvatar.vue";
import { formatBytes } from "@/utils";
import { useDisplay } from "vuetify";

// Props
withDefaults(
  defineProps<{
    rom: SimpleRom;
    withAvatar?: boolean;
    withName?: boolean;
    withFilename?: boolean;
    withSize?: boolean;
    withLink?: boolean;
  }>(),
  {
    withAvatar: true,
    withName: true,
    withFilename: false,
    withSize: true,
    withLink: false,
  },
);
</script>
<template>
  <v-list-item
    v-bind="{
      ...(withLink && rom
        ? {
            to: { name: 'rom', params: { rom: rom.id } },
          }
        : {}),
    }"
  >
    <template v-if="withAvatar" #prepend>
      <slot name="prepend"></slot>
      <r-avatar-rom :rom="rom" />
    </template>
    <v-row v-if="withName" no-gutters
      ><v-col>{{ rom.name }}</v-col></v-row
    >
    <v-row v-if="withFilename" no-gutters
      ><v-col class="text-romm-accent-1">{{ rom.file_name }}</v-col></v-row
    >
    <slot name="append-body"></slot>
    <template #append>
      <v-row no-gutters>
        <v-col v-if="withSize" cols="auto">
          <v-chip size="x-small" label>{{
            formatBytes(rom.file_size_bytes)
          }}</v-chip>
        </v-col>
        <v-col>
          <slot name="append"></slot>
        </v-col>
      </v-row>
    </template>
  </v-list-item>
</template>
