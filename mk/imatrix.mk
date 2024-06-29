#imatrix_default_dataset := 20k_random_data.txt
imatrix_default_dataset := groups_merged.txt

IMATRIX_DATASET := $(or $(IMATRIX_DATASET),$(imatrix_default_dataset))
IMATRIX_OPTS := $(if $(IMATRIX_CHUNKS),--chunks $(IMATRIX_CHUNKS)) $(IMATRIX_OPTS)

IQUANTS := $(patsubst %,$(QUANTMODEL).%.xguf,$(IQTYPES))
QUANTS += $(IQUANTS)

imatrix_data := $(DATADIR)/$(IMATRIX_DATASET)
imatrix_input := imatrix_dataset.txt
imatrix = $(TOASTER_BIN)/imatrix $(IMATRIX_OPTS) -m $1 $(ngl) -f $(imatrix_input) -o $2.tmp && mv $2.tmp $2

imat: $Q.imatrix

$(QUANTS):| $Q.imatrix

$(imatrix_input):
	cp $(imatrix_data) $@

%.imatrix: | %.bin $(imatrix_input)
	$(call imatrix,$*.bin,$@)

$(IQUANTS): %.xguf:
	$(call quantize,--imatrix $Q.imatrix $Q.bin,$@)
