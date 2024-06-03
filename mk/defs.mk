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

AUTHOR := $(or $(AUTHOR),$(firstword $(subst /, ,$(BASEREPO))))
BASEMODEL := $(or $(BASEMODEL),$(notdir $(BASEREPO)))
QUANTMODEL := $(or $(QUANTMODEL),$(BASEMODEL))
QUANTREPO := $(or $(QUANTREPO),$(ORGANIZATION)/$(QUANTMODEL)-GGUF)

IMATRIX_DATASET := $(or $(IMATRIX_DATASET),20k_random_data.txt)
IMATRIX_OPTS := $(if $(IMATRIX_CHUNKS),--chunks $(IMATRIX_CHUNKS)) $(IMATRIX_OPTS)

mkreadme_opts :=
mkreadme_opts += $(if $(DESCRIPTION),--description $(DESCRIPTION))
mkreadme_opts += $(if $(AUTHOR),--author $(AUTHOR))
mkreadme_opts += $(if $(FULLNAME),--title $(FULLNAME))

IQTYPES := IQ1_S IQ1_M IQ2_XXS IQ2_XS IQ2_S IQ2_M IQ3_XXS IQ3_XS IQ3_S IQ3_M IQ4_XS
KQTYPES := Q3_K_S Q3_K_M Q3_K_L Q4_K_S Q4_K_M Q5_K_S Q5_K_M Q6_K Q8_0

qtype = $(patsubst $(QUANTMODEL).%.gguf,%,$1)

IQUANTS := $(patsubst %,$(QUANTMODEL).%.gguf,$(IQTYPES))
KQUANTS := $(patsubst %,$(QUANTMODEL).%.gguf,$(KQTYPES))
QUANTS := $(IQUANTS) $(KQUANTS)
ASSETS := $(notdir $(wildcard $(ASSETDIR)/*.png))
HASHES := $(patsubst %,%.hash,$(QUANTS))

convert_py := convert-hf-to-gguf.py $(if $(PRETOKENIZER),--fallback-pre=$(PRETOKENIZER))
xconvert = python $(TOASTER_BIN)/$1 --outtype=$(or $3,auto) --outfile=$4 $(CONVERT_OPTS) $2
convert = $(call xconvert,$(convert_py),$1,$2,$3)
imatrix_data := $(DATADIR)/$(IMATRIX_DATASET)
imatrix_input := imatrix_dataset.txt
imatrix = $(TOASTER_BIN)/imatrix $(IMATRIX_OPTS) -c 128 -m $1 -f $(imatrix_input) -o $2.tmp && mv $2.tmp $2
mkreadme := python $(SCRIPTDIR)/mkreadme.py
quantize = $(TOASTER_BIN)/quantize $1 $2 $(call qtype,$2)

all:: quants
bin:: $(QUANTMODEL).bin
imat:: $(QUANTMODEL).imatrix
quants:: assets bin imat
quants:: $(QUANTS)
assets:: $(ASSETS) README.md
hashes:: $(HASHES)

$(QUANTMODEL).bin: | $(source)/$(BASEMODEL)
	$(call convert,$|,$(FTYPE),$@)

$(QUANTS):| $(QUANTMODEL).bin $(QUANTMODEL).imatrix

$(IQUANTS): %.gguf:
	$(call quantize,--imatrix $*.imatrix $*.bin,$@)

$(KQUANTS): %.gguf:
	$(call quantize,$*.bin,$@)

$(HASHES): %.hash: %
	sha256sum $< | cut -f1 -d' ' > $@.tmp && mv -f $@.tmp $@

meta.mk: $(QUANTMODEL).bin
	python $(MAKEDIR)/meta.py $< $@

$(imatrix_input):
	cp $(imatrix_data) $@

%.imatrix: | %.bin $(imatrix_input)
	$(call imatrix,$*.bin,$@)

$(ASSETS): %.png: | $(ASSETDIR)/%.png
	cp $| $@

README.md: GNUmakefile meta.mk

$(source)/$(BASEMODEL):
	mkdir -p $(@D)
	python $(SCRIPTDIR)/download_model.py $(BASEREPO) $@

.DELETE_ON_ERROR:

clean::
	$(if $(wildcard *.tmp),rm -f *.tmp)

include meta.mk

ifndef PARAMSIZE
ifdef model_paramsize
PARAMSIZE := $(model_paramsize)
endif
endif

ifdef PARAMSIZE
README.md:
	rm -f $@
	$(mkreadme) -p $(PARAMSIZE) $(mkreadme_opts) -o $@ $(BASEREPO)
endif
