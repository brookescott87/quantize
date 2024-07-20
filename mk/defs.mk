CURRENT_MAKEFILE := $(lastword $(MAKEFILE_LIST))
source := ./basemodel

parent = $(patsubst %/,%,$(dir $1))

ifndef BASEREPO
$(error BASEREPO is not set)
endif

ifndef TOASTER_ROOT
$(error TOASTER_ROOT is not set)
endif

S := $(call parent,$(call parent,$(CURRENT_MAKEFILE)))
T := $(TOASTER_ROOT)

ifndef ORGANIZATION
ifdef HF_DEFAULT_ORGANIZATION
ORGANIZATION := $(HF_DEFAULT_ORGANIZATION)
else
$(error ORGANIZATION is not set)
endif
endif

all:;

#imatrix_default_dataset := 20k_random_data.txt
imatrix_default_dataset := https://github.com/ggerganov/llama.cpp/files/15440637/groups_merged-enhancedV3.txt
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

IMATRIX_DATASET := $(or $(IMATRIX_DATASET),$(imatrix_default_dataset))
IMATRIX_OPTS := $(if $(IMATRIX_CHUNKS),--chunks $(IMATRIX_CHUNKS)) $(IMATRIX_OPTS)

PPL_DATASET := $(or $(PPL_DATASET),$(ppl_default_dataset))
ppl_input := $S/data/$(PPL_DATASET)

isurl = $(filter http://% https://% ftp://%,$1)

mkreadme_opts :=
mkreadme_opts += $(if $(DESCRIPTION),--description $(DESCRIPTION))
mkreadme_opts += $(if $(AUTHOR),--author $(AUTHOR))
mkreadme_opts += $(if $(FULLNAME),--title $(FULLNAME))

ngl := $(addprefix -ngl ,$(or $(NGL),$(N_GPU_LAYERS)))

IQTYPES := IQ1_S IQ1_M IQ2_XXS IQ2_XS IQ2_S IQ2_M IQ3_XXS IQ3_XS IQ3_S IQ3_M IQ4_XS
KQTYPES := Q3_K_S Q3_K_M Q3_K_L Q4_K_S Q4_K_M Q5_K_S Q5_K_M Q6_K $(filter-out $(FTYPE),Q8_0)

qtype = $(firstword $(subst ., ,$(patsubst $(QUANTMODEL).%,%,$1)))

ifndef NO_IMATRIX
IQUANTS := $(patsubst %,$(QUANTMODEL).%.xguf,$(IQTYPES))
endif
KQUANTS := $(patsubst %,$(QUANTMODEL).%.xguf,$(KQTYPES))
QUANTS := $(IQUANTS) $(KQUANTS)
PPLOUT := $(patsubst %.xguf,%.ppl.out,$(QUANTS))
ASSETS := $(notdir $(wildcard $S/assets/*.png))

convert_py := convert_hf_to_gguf.py $(if $(PRETOKENIZER),--vocab-pre=$(PRETOKENIZER))
xconvert = python $T/bin/$1 --outtype=$3 --outfile=$(patsubst $Q.auto,$Q.{FTYPE},$4) $(CONVERT_OPTS) $2
convert = $(call xconvert,$(convert_py),$1,$2,$3)
imatrix_rename := python $S/imatrix_rename.py
imatrix_data := $(notdir $(IMATRIX_DATASET))
imatrix_url := $(call isurl,$(IMATRIX_DATASET))
imatrix_src := $(or $(imatrix_url),$(imatrix_data))
imatrix_input := $S/data/$(imatrix_data)
imatrix = $T/bin/llama-imatrix $(IMATRIX_OPTS) -m $1 $(ngl) -f $(imatrix_input) -o $2
mkreadme := python $S/mkreadme.py
qupload := python $S/qupload.py
postquantize := python $S/postquantize.py
quantize = $T/bin/llama-quantize $1 $2 $(call qtype,$2)

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

.SUFFIXES:
.SECONDARY:
.DELETE_ON_ERROR:

ifdef DOWNLOAD
$(source)/$(BASEMODEL):
	mkdir -p $(@D)
	python $S/download_model.py $(BASEREPO) $@
endif

$Q.$F.xguf-in: | $B
	test -f $@ || $(call convert,$B,$F,$@)

$Q.bin: $Q.$F.xguf-in
	rm -f $@ && ln $< $@

$(QUANTS:=-in):| $Q.bin

ifndef NO_IMATRIX
$(QUANTS:=-in):| $Q.imatrix

ifdef imatrix_url
$(imatrix_input):
	wget -O $@ "${imatrix_url}"
endif

%.imatrix: | %.bin $(imatrix_input)
	$(call imatrix,$*.bin,$@.tmp) && $(imatrix_rename) --dataset $(imatrix_src) $@.tmp $@
endif

_meta.json: $Q.bin
	python $S/mk/meta.py $(META_OPTS) $@ $<

%.klb: %.bin $(ppl_input)
	$(llama-perplexity) -sm none -m $< -f $(ppl_input) --kl-divergence-base $@.tmp && rm -f $@.sav && ln $@.tmp $@.sav && mv -f $@.tmp $@

$(ASSETS): %.png: | $S/assets/%.png
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
