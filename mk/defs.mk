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

ppl_default_dataset := wiki_test.txt
#default_ftype := auto
default_ftype := f32

AUTHOR := $(or $(AUTHOR),$(firstword $(subst /, ,$(BASEREPO))))
BASEMODEL := $(or $(BASEMODEL),$(notdir $(BASEREPO)))
QUANTMODEL := $(or $(QUANTMODEL),$(BASEMODEL))
QUANTREPO := $(or $(QUANTREPO),$(QUANTMODEL)-GGUF)

FTYPE := $(or $(FTYPE),$(default_ftype))

PPL_DATASET := $(or $(PPL_DATASET),$(ppl_default_dataset))
ppl_input := $(DATADIR)/$(PPL_DATASET)

mkreadme_opts :=
mkreadme_opts += $(if $(DESCRIPTION),--description $(DESCRIPTION))
mkreadme_opts += $(if $(AUTHOR),--author $(AUTHOR))
mkreadme_opts += $(if $(FULLNAME),--title $(FULLNAME))

ngl := $(addprefix -ngl ,$(or $(NGL),$(N_GPU_LAYERS)))

IQTYPES := IQ1_S IQ1_M IQ2_XXS IQ2_XS IQ2_S IQ2_M IQ3_XXS IQ3_XS IQ3_S IQ3_M IQ4_XS
KQTYPES := Q3_K_S Q3_K_M Q3_K_L Q4_K_S Q4_K_M Q5_K_S Q5_K_M Q6_K Q8_0

KQUANTS := $(patsubst %,$(QUANTMODEL).%.xguf,$(KQTYPES))
QUANTS := $(KQUANTS)
PPLOUT := $(patsubst %.xguf,%.ppl.out,$(QUANTS))
ASSETS := $(notdir $(wildcard $(ASSETDIR)/*.png))

qtype = $(patsubst $(QUANTMODEL).%.xguf,%,$1)
convert_py := convert-hf-to-gguf.py $(if $(PRETOKENIZER),--vocab-pre=$(PRETOKENIZER))
xconvert = python $(TOASTER_BIN)/$1 --outtype=$(or $3,auto) --outfile=$4 $(CONVERT_OPTS) $2
convert = $(call xconvert,$(convert_py),$1,$2,$3-in) && $(postquantize) $3-in $3
mkreadme := python $(SCRIPTDIR)/mkreadme.py
qupload := python $(SCRIPTDIR)/qupload.py
postquantize := python $(SCRIPTDIR)/postquantize.py
quantize = $(TOASTER_BIN)/quantize $1 $2-in $(call qtype,$2) && $(postquantize) $2-in $2

B := $(source)/$(BASEMODEL)
Q := $(QUANTMODEL)

all: quants
bin: $Q.bin
imat: bin
klb: $Q.klb
ppl: $(PPLOUT)
quants: bin imat $(QUANTS)
assets: $(ASSETS) README.md

clean:
	$(if $(wildcard *.tmp),rm -f *.tmp)

upload: assets
	$(qupload) -i -p -R $(QUANTREPO) .

.PHONY: all bin imat klb ppl quants assets clean upload

.DELETE_ON_ERROR:

ifdef DOWNLOAD
$(source)/$(BASEMODEL):
	mkdir -p $(@D)
	python $(SCRIPTDIR)/download_model.py $(BASEREPO) $@
endif

$Q.bin: | $B
	test -f $@ || $(call convert,$B,$(FTYPE),$@)

$(QUANTS):| $Q.bin

ifndef NO_IMATRIX
include imatrix.mk
endif

_meta.json: $Q.bin
	python $(MAKEDIR)/meta.py $(META_OPTS) $@ $<

%.klb: %.bin $(ppl_input)
	$(perplexity) -sm none -m $< -f $(ppl_input) --kl-divergence-base $@.tmp && rm -f $@.sav && ln $@.tmp $@.sav && mv -f $@.tmp $@

$(ASSETS): %.png: | $(ASSETDIR)/%.png
	cp $| $@

README.md: _meta.json GNUmakefile
	rm -f $@
	$(mkreadme) -m $< $(mkreadme_opts) -o $@ $(BASEREPO)

$(KQUANTS): %.xguf:
	$(call quantize,$Q.bin,$@)

%.ppl.out: %.xguf $Q.klb
	$(perplexity) -m $< $(ngl) --kl-divergence --kl-divergence-base $Q.klb | tee $@.tmp && mv -f $@.tmp $@
