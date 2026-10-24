# Legacy KGSL memtrack

Replaces the Qualcomm AIDL service on this SMMU-based SM7125 device. Per-process
GL and GRAPHICS queries retain the KGSL mapped/unmapped and imported counters.
PID-zero GL queries report nonsecure GPU-private memory using:

    page_alloc - sum(process gpumem_mapped) + coherent

`page_alloc` includes process allocations and driver-global page allocations.
`coherent` covers separate contiguous driver allocations; their PFNMAP mappings
are not counted by CPU smaps. Imported DMA buffers are outside these counters.
Do not add `vmalloc`: it measures mappings of the same pages. The separate
`secure` counter is returned with the secure-memory flag. This formula depends
on this device's SMMU allocation paths; recheck before reuse without an MMU.

Reads are not an atomic snapshot. Process exits are tolerated; malformed
counters, overflow, and mapped totals exceeding allocations return errors
rather than a fabricated zero. This service does not supply the separate GPU
BPF total map used by some framework memory statistics.

Kernel references in `drivers/gpu/msm`: `kgsl_allocate_user`,
`kgsl_allocate_global`, `kgsl_sharedmem_page_alloc_user`,
`kgsl_sharedmem_alloc_contig`, `get_mmap_entry`, `kgsl_gpumem_vm_close`.

Run `python3 memtrack/tests/test_memtrack.py` for native ASAN/UBSAN handler tests.
A ROM build and enforcing-device service/VTS checks are required for integration
validation.
