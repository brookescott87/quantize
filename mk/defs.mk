source := ./basemodel

parent = $(patsubst %/,%,$(dir $1))

MAKEDIR := $(call parent,$(lastword $(MAKEFILE_LIST)))
SRCDIR := $(call parent,$(MAKEDIR))
SCRIPTDIR := $(SRCDIR)
DATADIR := $(SRCDIR)/data
ASSETDIR := $(SRCDIR)/assets

ifndef BASEREPO
$(error BASEREPO is not set)
endif

ifndef TOASTER_ROOT
$(error TOASTER_ROOT is not set)
endif

export TOASTER_BIN := $(TOASTER_ROOT)/bin
export TOASTER_LIB := $(TOASTER_ROOT)/lib

ifndef ORGANIZATION
ifdef HF_DEFAULT_ORGANIZATION
ORGANIZATION := $(HF_DEFAULT_ORGANIZATION)
else
$(error ORGANIZATION is not set)
endif
endif

all:;

#imatrix_default_dataset := 20k_random_data.txt
imatrix_default_dataset := groups_merged.txt
ppl_default_dataset := wiki_test.txt
#default_ftype := auto
default_ftype := F32

FTYPE := $(or $(FTYPE),$(default_ftype),auto)

AUTHOR := $(or $(AUTHOR),$(firstword $(subst /, ,$(BASEREPO))))
BASEMODEL := $(or $(BASEMODEL),$(notdir $(BASEREPO)))
QUANTMODEL := $(or $(QUANTMODEL),$(BASEMODEL))
QUANTREPO := $(or $(QUANTREPO),$(QUANTMODEL)-GGUF)

B := $(source)/$(BASEMODEL)
Q := $(QUANTMODEL)
F := $(FTYPE)

ngl := $(addprefix -ngl ,$(or $(NGL),$(N_GPU_LAYERS)))

IMATRIX_DATASET := $(or $(IMATRIX_DATASET),$(imatrix_default_dataset))
IMATRIX_OPTS := $(if $(IMATRIX_CHUNKS),--chunks $(IMATRIX_CHUNKS)) $(IMATRIX_OPTS)

PPL_DATASET := $(or $(PPL_DATASET),$(ppl_default_dataset))
ppl_input := $(DATADIR)/$(PPL_DATASET)

mkreadme_opts :=
mkreadme_opts += $(if $(DESCRIPTION),--description $(DESCRIPTION))
mkreadme_opts += $(if $(AUTHOR),--author $(AUTHOR))
mkreadme_opts += $(if $(FULLNAME),--title $(FULLNAME))

IQTYPES := IQ1_S IQ1_M IQ2_XXS IQ2_XS IQ2_S IQ2_M IQ3_XXS IQ3_XS IQ3_S IQ3_M IQ4_XS
KQTYPES := Q3_K_S Q3_K_M Q3_K_L Q4_K_S Q4_K_M Q5_K_S Q5_K_M Q6_K $(filter-out $(FTYPE),Q8_0)

qtype = $(firstword $(subst ., ,$(patsubst $(QUANTMODEL).%,%,$1)))

ifndef NO_IMATRIX
IQUANTS := $(patsubst %,$(QUANTMODEL).%.xguf,$(IQTYPES))
endif
KQUANTS := $(patsubst %,$(QUANTMODEL).%.xguf,$(KQTYPES))
QUANTS := $(IQUANTS) $(KQUANTS)
PPLOUT := $(patsubst %.xguf,%.ppl.out,$(QUANTS))
ASSETS := $(notdir $(wildcard $(ASSETDIR)/*.png))

convert_py := convert_hf_to_gguf.py $(if $(PRETOKENIZER),--vocab-pre=$(PRETOKENIZER))
xconvert = python $(TOASTER_BIN)/$1 --outtype=$3 --outfile=$(patsubst $Q.auto,$Q.{FTYPE},$4) $(CONVERT_OPTS) $2
convert = $(call xconvert,$(convert_py),$1,$2,$3)
imatrix_data := $(DATADIR)/$(IMATRIX_DATASET)
imatrix_input := imatrix_dataset.txt
imatrix = $(TOASTER_BIN)/llama-imatrix $(IMATRIX_OPTS) -m $1 $(ngl) -f $(imatrix_input) -o $2.tmp && mv $2.tmp $2
mkreadme := python $(SCRIPTDIR)/mkreadme.py
qupload := python $(SCRIPTDIR)/qupload.py
postquantize := python $(SCRIPTDIR)/postquantize.py
quantize = $(TOASTER_BIN)/llama-quantize $1 $2 $(call qtype,$2)

bin imat: $Q.bin
ifndef NO_IMATRIX
imat: $Q.imatrix
endif
klb: $Q.klb
ppl: $(PPLOUT)
all quants: $Q.$F.xguf
all quants: $(QUANTS)
all assets: $(ASSETS) README.md

tidy:
	rm -f *.tmp tmp

clean: tidy
	rm -f *.xguf *.xguf-in *.gguf *.sha256 *.bin *.imatrix *.png *.json *.md imatrix_dataset.txt

upload: assets
	$(qupload) -i -p -R $(QUANTREPO) .

.PHONY: all bin imat klb ppl quants assets clean tidy upload

.SECONDARY:
.DELETE_ON_ERROR:

$(source)/$(BASEMODEL):
	mkdir -p $(@D)
	python $(SCRIPTDIR)/download_model.py $(BASEREPO) $@

$Q.$F.xguf-in: | $B
	test -f $@ || $(call convert,$B,$F,$@)

$Q.bin: $Q.$F.xguf-in
	rm -f $@ && ln $< $@

$(QUANTS):| $Q.bin

ifndef NO_IMATRIX
$(QUANTS):| $Q.imatrix

$(imatrix_input):
	cp $(imatrix_data) $@

%.imatrix: | %.bin $(imatrix_input)
	$(call imatrix,$*.bin,$@)
endif

_meta.json: $Q.bin
	python $(MAKEDIR)/meta.py $(META_OPTS) $@ $<

%.klb: %.bin $(ppl_input)
	$(llama-perplexity) -sm none -m $< -f $(ppl_input) --kl-divergence-base $@.tmp && rm -f $@.sav && ln $@.tmp $@.sav && mv -f $@.tmp $@

$(ASSETS): %.png: | $(ASSETDIR)/%.png
	cp $| $@

README.md: _meta.json GNUmakefile
	rm -f $@
	$(mkreadme) -m $< $(mkreadme_opts) -o $@ $(BASEREPO)

ifndef NO_IMATRIX
$(IQUANTS:=-in): %:
	$(call quantize,--imatrix $Q.imatrix $Q.bin,$@)
endif

$(KQUANTS:=-in): %:
	$(call quantize,$Q.bin,$@)

%.xguf: %.xguf-in
	$(postquantize) $< $@

%.ppl.out: %.xguf $Q.klb
	$(llama-perplexity) -m $< $(ngl) --kl-divergence --kl-divergence-base $Q.klb | tee $@.tmp && mv -f $@.tmp $@
