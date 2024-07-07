SRCDIR := $(patsubst %/,%,$(dir $(lastword $(MAKEFILE_LIST))))
SCRIPTDIR := $(SRCDIR)
DATADIR := $(SRCDIR)/data
ASSETS := $(SRCDIR)/assets
MODELBASE := $(SRCDIR)/models/base

ifndef TOASTER_ROOT
$(error TOASTER_ROOT is not set)
endif

export TOASTER_BIN := $(TOASTER_ROOT)/bin
export TOASTER_LIB := $(TOASTER_ROOT)/lib

ifndef HF_ORGANIZATION
ifdef HF_DEFAULT_ORGANIZATION
export HF_ORGANIZATION := $(HF_DEFAULT_ORGANIZATION)
else
$(error HF_ORGANIZATION is not set)
endif
endif

export OUTPUT_ROOT := output/$(HF_ORGANIZATION)

QTYPES := IQ1_S IQ1_M IQ2_XXS IQ2_XS IQ2_S IQ2_M Q2_K_S Q2_K
QTYPES += IQ3_XXS IQ3_XS Q3_K_S IQ3_S IQ3_M Q3_K_M Q3_K_L IQ4_XS
QTYPES += Q4_K_S Q4_K_M Q5_K_S Q5_K_M Q6_K Q8_0

QSUFFIXES := $(addsuffix .gguf,$(QTYPES))

listqtypes::
	@echo $(QTYPES)

xcombine = $(foreach a,$1,$(foreach b,$2,$a$b))

qtype = $(subst .,,$(suffix $(patsubst %.gguf,%,$1)))

ifndef MODELS
MODELS := $(notdir $(wildcard $(MODELBASE)/*))
endif

ifdef OUTPUT_ROOT
OUTPUTDIRS := $(patsubst %,$(OUTPUT_ROOT)/%-GGUF,$(MODELS))
MODELSTEMS := $(foreach m,$(MODELS),$(OUTPUT_ROOT)/$m-GGUF/$m.)
else
OUTPUTDIRS :=
MODELSTEMS := $(patsubst %,%.,$(MODELS))
endif
OUTPUTQUANTS := $(call xcombine,$(MODELSTEMS),$(QSUFFIXES))

listquants::
	@for q in $(OUTPUTQUANTS); do echo $$q; done

listmodels::
	@echo "Models: $(MODELS)"
	@echo "Stems: $(MODELSTEMS)"

xinstall = mkdir -p $3 && $1 $2 $3

ifdef INSTALL_DIR
VPATH := $(patsubst %,$(INSTALL_DIR)/%-GGUF,$(MODELS))
install = python $(SCRIPTDIR)/install.py $3 $1 $(INSTALL_DIR)/$2
else
install = true
endif

# xquantize($1=out, $2=type, $3=in[, $4=imat])
xquantize = \
	$(TOASTER_BIN)/quantize --imatrix $4 $3 $1 $2

# quantize($1=base, $2=ins, $3=out, $4=install opts)
quantize = \
	$(call xquantize,$3,$(call qtype,$3),$(filter %.bin,$2),$(filter %.imatrix,$2)) && $(call install,$3,$1-GGUF,$4)

xconvert = python $(TOASTER_BIN)/$1 --outtype=$(or $3,$(defftype)) --outfile=$4 $(convert_opts) $2

ifdef old_convert
convert_py := convert.py --pad-vocab
defftype := fp16
else
convert_py := convert_hf_to_gguf.py $(if $(PRETOKENIZER),--fallback-pre=$(PRETOKENIZER))
defftype := auto
endif

convert = $(call xconvert,$(convert_py),$1,$2,$3)
imatrix_data := $(DATADIR)/20k_random_data.txt
imatrix = $(TOASTER_BIN)/imatrix --chunks 128 -c 128 -m $(filter %.bin,$1) -f $(filter %.txt,$1) -o $2.tmp && mv $2.tmp $2
mkreadme := python $(SCRIPTDIR)/mkreadme.py

ifdef ABORT
$(error Aborted)
endif

readme:: $(addsuffix /README.md,$(OUTPUTDIRS))
bin:: $(addsuffix bin,$(MODELSTEMS))
q8:: $(addsuffix Q8_0.gguf,$(MODELSTEMS))
imat:: $(addsuffix imatrix,$(MODELSTEMS))

quants:: readme bin imat
quants:: $(call xcombine,$(MODELSTEMS),$(QSUFFIXES))
all:: quants

$(OUTPUTDIRS): $(OUTPUT_ROOT)/%-GGUF:
	mkdir -p $@ && cp $(wildcard $(ASSETS)/*.png) $@ 

$(OUTPUT_ROOT)/%-GGUF/README.md: | $(MODELBASE)/% $(OUTPUT_ROOT)/%-GGUF
	$(mkreadme) -o $@ -f $(MODELBASE)/$*

%.bin: | $(OUTPUTDIRS)
	$(call convert,$(MODELBASE)/$(notdir $*),$(FTYPE),$@)

%.imatrix:| %.bin imatrix_dataset.txt
	$(call imatrix,$|,$@)

imatrix_dataset.txt:
	cp $(imatrix_data) $@

.DELETE_ON_ERROR:

%.Q2_K.gguf:| %.bin %.imatrix
	$(call quantize,$*,$|,$@)
%.Q3_K_S.gguf:| %.bin %.imatrix
	$(call quantize,$*,$|,$@)
%.Q3_K_M.gguf:| %.bin %.imatrix
	$(call quantize,$*,$|,$@)
%.Q3_K_L.gguf:| %.bin %.imatrix
	$(call quantize,$*,$|,$@)
%.Q4_K_S.gguf:| %.bin %.imatrix
	$(call quantize,$*,$|,$@)
%.Q4_K_M.gguf:| %.bin %.imatrix
	$(call quantize,$*,$|,$@)
%.Q5_K_S.gguf:| %.bin %.imatrix
	$(call quantize,$*,$|,$@)
%.Q5_K_M.gguf:| %.bin %.imatrix
	$(call quantize,$*,$|,$@)
%.Q6_K.gguf:| %.bin %.imatrix
	$(call quantize,$*,$|,$@)
%.Q8_0.gguf:| %.bin %.imatrix
	$(call quantize,$*,$|,$@)
%.Q2_K_S.gguf:| %.bin %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ2_XXS.gguf:| %.bin %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ2_XS.gguf:| %.bin %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ3_XS.gguf:| %.bin %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ3_XXS.gguf:| %.bin %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ1_S.gguf:| %.bin %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ1_M.gguf:| %.bin %.imatrix
	$(call quantize,$*,$|,$@)
# %.IQ4_NL.gguf:| %.bin %.imatrix
# 	$(call quantize,$*,$|,$@)
%.IQ3_S.gguf:| %.bin %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ3_M.gguf:| %.bin %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ2_S.gguf:| %.bin %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ2_M.gguf:| %.bin %.imatrix
	$(call quantize,$*,$|,$@)
%.IQ4_XS.gguf:| %.bin %.imatrix
	$(call quantize,$*,$|,$@)
